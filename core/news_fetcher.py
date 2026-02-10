# core/hybrid_news_fetcher.py
import requests
import feedparser
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from .models import Post, Category, User
import logging
import re
from bs4 import BeautifulSoup
import random
from time import sleep

logger = logging.getLogger(__name__)


class NewsFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.articles = []
        
    def fetch_all_news(self):
        """Fetch news using multiple methods"""
        logger.info("Starting hybrid news fetch...")
        
        # Define all fetching methods with weights
        methods = [
            (self.fetch_google_news_scrape, 3),      # Google scrape (most reliable)
            (self.fetch_rss_feeds, 3),               # RSS feeds (reliable)
            (self.fetch_newsapi_general, 2),         # NewsAPI general
            (self.fetch_web_scrape, 1),              # Direct website scrape
            (self.fetch_reddit_news, 1),             # Reddit Nigeria news
            (self.fetch_african_news, 2),           # Add African news sources
        ]
        
        # Execute methods with random delays to avoid rate limiting
        for method, weight in methods:
            try:
                logger.info(f"Executing: {method.__name__}")
                sleep(random.uniform(1, 3))  # Random delay
                method()
            except Exception as e:
                logger.error(f"Error in {method.__name__}: {e}")
                continue
        
        # Remove duplicates
        unique_articles = self.remove_duplicates(self.articles)
        
        # Save to database
        saved_count = self.save_articles(unique_articles)
        
        logger.info(f"Total articles found: {len(unique_articles)}")
        logger.info(f"Articles saved: {saved_count}")
        
        return saved_count

    def fetch_african_news(self):
        """Fetch additional African news sources"""
        try:
            african_sources = [
                ('Africa News', 'https://www.africanews.com/feed/rss', 'Africa'),
                ('Sahara Reporters', 'https://saharareporters.com/feeds/latest/feed', 'Nigeria'),
                ('Daily Trust', 'https://dailytrust.com/feed/', 'Nigeria'),
                ('Business Day', 'https://businessday.ng/feed/', 'Economy'),
                ('Leadership', 'https://leadership.ng/feed/', 'Nigeria'),
                ('Independent NG', 'https://independent.ng/feed/', 'Nigeria'),
                ('Nairametrics', 'https://nairametrics.com/feed/', 'Economy'),
                ('TechCabal', 'https://techcabal.com/feed/', 'Technology'),
            ]
            
            for source_name, feed_url, category in african_sources:
                try:
                    feed = feedparser.parse(feed_url)
                    
                    for entry in feed.entries[:15]:  # Get more entries
                        title = entry.title if hasattr(entry, 'title') else ''
                        
                        content = ''
                        if hasattr(entry, 'summary'):
                            content = entry.summary
                        elif hasattr(entry, 'description'):
                            content = entry.description
                        
                        # Clean HTML
                        import re
                        content = re.sub('<[^<]+?>', '', content)
                        
                        # Get image
                        image_url = ''
                        if hasattr(entry, 'media_content'):
                            for media in entry.media_content:
                                if media.get('medium') == 'image' and media.get('url'):
                                    image_url = media.get('url')
                                    break
                        
                        if not image_url and hasattr(entry, 'enclosures'):
                            for enc in entry.enclosures:
                                if enc.get('type', '').startswith('image/'):
                                    image_url = enc.get('href', '')
                                    break
                        
                        if not image_url and content:
                            img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
                            if img_match:
                                image_url = img_match.group(1)
                        
                        if not image_url and hasattr(entry, 'link'):
                            image_url = self.extract_image_from_url(entry.link)
                        
                        self.articles.append({
                            'title': title,
                            'content': content[:500] if content else title,
                            'url': entry.link if hasattr(entry, 'link') else '',
                            'source': source_name,
                            'image_url': image_url,
                            'published_at': entry.published if hasattr(entry, 'published') else '',
                            'category': category,
                            'method': 'rss'
                        })
                        
                except Exception as e:
                    print(f"Error fetching {source_name}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in African news fetch: {e}")
    
    def fetch_google_news_scrape(self):
        """Scrape Google News for Nigeria and mark trending as banners"""
        try:
            # Google News Nigeria search
            search_terms = [
                'Nigeria+news',
                'Nigeria+politics',
                'Nigeria+economy',
                'Nigeria+technology',
                'Lagos+news',
                'Abuja+news'
            ]
            
            for term in search_terms:
                try:
                    url = f"https://news.google.com/rss/search?q={term}&hl=en-NG&gl=NG&ceid=NG:en"
                    feed = feedparser.parse(url)
                    
                    for entry in feed.entries[:15]:  # Get more entries
                        title = entry.title if hasattr(entry, 'title') else ''
                        link = entry.link if hasattr(entry, 'link') else ''
                        
                        if not title or not link:
                            continue
                        
                        # Extract source from title (Google News format)
                        source = 'Google News'
                        if ' - ' in title:
                            parts = title.split(' - ')
                            title = parts[0].strip()
                            source = parts[-1].strip()
                        
                        content = ''
                        if hasattr(entry, 'summary'):
                            content = entry.summary
                        
                        # Clean HTML
                        import re
                        content = re.sub('<[^<]+?>', '', content)
                        
                        # Get image - try multiple methods
                        image_url = ''
                        
                        # 1. Try to extract from content
                        if content:
                            img_match = re.search(r'src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"', content)
                            if img_match:
                                image_url = img_match.group(1)
                        
                        # 2. If no image in content, try to extract from article
                        if not image_url and 'news.google.com' not in link:
                            image_url = self.extract_image_from_url(link)
                        
                        # 3. If still no image, use a placeholder based on category
                        if not image_url:
                            category = self.detect_category(title)
                            image_url = self.get_category_placeholder(category)
                        
                        is_trending = any(keyword in title.lower() for keyword in [
                            'breaking', 'exclusive', 'latest', 'happening now',
                            'urgent', 'alert', 'crisis', 'emergency'
                        ])
                        
                        self.articles.append({
                            'title': title,
                            'content': content[:500] if content else title,
                            'url': link,
                            'source': source,
                            'image_url': image_url,
                            'published_at': entry.published if hasattr(entry, 'published') else '',
                            'category': self.detect_category(title),
                            'method': 'google_scrape',
                            'is_banner': is_trending 
                        })
                        
                except Exception as e:
                    print(f"Error with search term {term}: {e}")
                    continue
                        
        except Exception as e:
            print(f"Error in Google News scrape: {e}")
        
    def get_category_placeholder(self, category):
        """Get a placeholder image based on category"""
        placeholders = {
            'Politics': 'https://images.unsplash.com/photo-1551135049-8a33b2fb2f7f?w=800&q=80',
            'Economy': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w-800&q-80',
            'Sports': 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800&q=80',
            'Technology': 'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=800&q=80',
            'Entertainment': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&q=80',
            'News': 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&q=80',
        }
        return placeholders.get(category, 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&q=80')
    
    def extract_image_from_url(self, url):
            """Extract image from article URL using multiple methods"""
            try:
                response = self.session.get(url, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Try multiple methods to get image
                    image_sources = []
                    
                    # 1. Open Graph image (most reliable)
                    meta_image = soup.find('meta', property='og:image')
                    if meta_image and meta_image.get('content'):
                        image_sources.append(meta_image.get('content'))
                    
                    # 2. Twitter card image
                    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                    if twitter_image and twitter_image.get('content'):
                        image_sources.append(twitter_image.get('content'))
                    
                    # 3. Schema.org image
                    schema_image = soup.find('meta', itemprop='image')
                    if schema_image and schema_image.get('content'):
                        image_sources.append(schema_image.get('content'))
                    
                    # 4. First article image with reasonable size
                    article_images = soup.find_all('img')
                    for img in article_images:
                        src = img.get('src') or img.get('data-src')
                        if src:
                            # Check if it's likely a content image (not icon/logo)
                            img_class = img.get('class', [])
                            img_id = img.get('id', '')
                            img_alt = img.get('alt', '').lower()
                            
                            # Skip small images and icons
                            if any(keyword in str(img_class).lower() for keyword in ['icon', 'logo', 'avatar']):
                                continue
                            if any(keyword in img_id.lower() for keyword in ['icon', 'logo']):
                                continue
                            
                            # Make URL absolute if relative
                            if src.startswith('//'):
                                src = 'https:' + src
                            elif src.startswith('/'):
                                # Get base URL
                                from urllib.parse import urlparse
                                parsed = urlparse(url)
                                src = f"{parsed.scheme}://{parsed.netloc}{src}"
                            
                            image_sources.append(src)
                    
                    # Return the first valid image
                    for img_url in image_sources:
                        if img_url and self.is_valid_image_url(img_url):
                            return img_url
                            
            except Exception as e:
                print(f"[IMAGE EXTRACTION] Error extracting image from {url}: {e}")
            
            return ''

    def is_valid_image_url(self, url):
            """Check if URL is likely a valid image"""
            if not url:
                return False
            
            # Check common image extensions
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
            url_lower = url.lower()
            
            for ext in image_extensions:
                if ext in url_lower:
                    return True
            
            # Check for common image CDN patterns
            image_patterns = ['images.unsplash.com', 'i.imgur.com', 'cdn.', 'media.', '/images/', '/img/', 'photo', 'image']
            for pattern in image_patterns:
                if pattern in url_lower:
                    return True
            
            return False

    def fetch_rss_feeds(self):
        """Fetch from multiple RSS feeds"""
        rss_feeds = [
            # Nigerian Newspapers
            ('Premium Times', 'https://www.premiumtimesng.com/feed/', 'Politics'),
            ('Vanguard', 'https://www.vanguardngr.com/feed/', 'News'),
            ('Punch', 'https://punchng.com/feed/', 'News'),
            ('Guardian Nigeria', 'https://guardian.ng/feed/', 'News'),
            ('This Day', 'https://www.thisdaylive.com/index.php/feed/', 'News'),
            ('The Nation', 'https://thenationonlineng.net/feed/', 'News'),
            
            # International with Nigeria coverage
            ('BBC Africa', 'http://feeds.bbci.co.uk/news/world/africa/rss.xml', 'Africa'),
            ('Reuters Africa', 'http://feeds.reuters.com/reuters/AFRICAfricaNews', 'Africa'),
            ('Al Jazeera', 'https://www.aljazeera.com/xml/rss/all.xml', 'International'),
            ('CNN Africa', 'http://rss.cnn.com/rss/edition_africa.rss', 'International'),
        ]
        
        for source_name, feed_url, category in rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:  # Get 10 from each source
                    title = entry.title if hasattr(entry, 'title') else ''
                    
                    # Filter for Nigeria in international feeds
                    if source_name in ['BBC Africa', 'Reuters Africa', 'CNN Africa', 'Al Jazeera']:
                        if not any(keyword in title.lower() for keyword in ['nigeria', 'nigerian', 'lagos', 'abuja']):
                            continue
                    
                    content = ''
                    if hasattr(entry, 'summary'):
                        content = entry.summary
                    elif hasattr(entry, 'description'):
                        content = entry.description
                    
                    # Clean HTML
                    import re
                    content = re.sub('<[^<]+?>', '', content)
                    
                    # Get image - improved extraction
                    image_url = ''
                    
                    # 1. Check for media content in RSS
                    if hasattr(entry, 'media_content'):
                        for media in entry.media_content:
                            if media.get('medium') == 'image' and media.get('url'):
                                image_url = media.get('url')
                                break
                    
                    # 2. Check for enclosures
                    if not image_url and hasattr(entry, 'enclosures'):
                        for enc in entry.enclosures:
                            if enc.get('type', '').startswith('image/'):
                                image_url = enc.get('href', '')
                                break
                    
                    # 3. Extract from content HTML
                    if not image_url and content:
                        # Look for img tags
                        img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
                        if img_match:
                            image_url = img_match.group(1)
                        else:
                            # Look for src attributes
                            src_match = re.search(r'src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"', content)
                            if src_match:
                                image_url = src_match.group(1)
                    
                    # 4. Try to extract from article URL
                    if not image_url and hasattr(entry, 'link'):
                        article_url = entry.link
                        if 'news.google.com' not in article_url:  # Don't scrape Google redirects
                            image_url = self.extract_image_from_url(article_url)
                    
                    # 5. Use category placeholder as last resort
                    if not image_url:
                        image_url = self.get_category_placeholder(category)
                    
                    self.articles.append({
                        'title': title,
                        'content': content[:500] if content else title,
                        'url': entry.link if hasattr(entry, 'link') else '',
                        'source': source_name,
                        'image_url': image_url,
                        'published_at': entry.published if hasattr(entry, 'published') else '',
                        'category': category,
                        'method': 'rss'
                    })
                    
            except Exception as e:
                print(f"Error fetching {source_name} RSS: {e}")
                continue
    
    def fetch_newsapi_general(self):
        """Fetch from NewsAPI using working endpoints"""
        if not hasattr(settings, 'NEWS_API_KEY') or not settings.NEWS_API_KEY:
            return
        
        # Endpoints that work
        endpoints = [
            ('US News', 'https://newsapi.org/v2/top-headlines?country=us&pageSize=15&apiKey=', 'International'),
            ('Business', 'https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=10&apiKey=', 'Business'),
            ('Technology', 'https://newsapi.org/v2/top-headlines?category=technology&language=en&pageSize=10&apiKey=', 'Technology'),
            ('Sports', 'https://newsapi.org/v2/top-headlines?category=sports&language=en&pageSize=10&apiKey=', 'Sports'),
            ('Entertainment', 'https://newsapi.org/v2/top-headlines?category=entertainment&language=en&pageSize=10&apiKey=', 'Entertainment'),
        ]
        
        for source_name, endpoint, category in endpoints:
            try:
                url = endpoint + settings.NEWS_API_KEY
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    for article in data.get('articles', []):
                        title = article.get('title', '')
                        
                        # Filter for Nigeria relevance
                        if category == 'International':
                            if not any(keyword in title.lower() for keyword in ['nigeria', 'africa', 'nigerian']):
                                continue
                        
                        self.articles.append({
                            'title': title,
                            'content': article.get('description') or article.get('content') or title,
                            'url': article.get('url'),
                            'source': article.get('source', {}).get('name', source_name),
                            'image_url': article.get('urlToImage', ''),
                            'published_at': article.get('publishedAt'),
                            'category': category,
                            'method': 'newsapi'
                        })
                        
            except Exception as e:
                logger.error(f"Error with NewsAPI {source_name}: {e}")
                continue
    
    def fetch_web_scrape(self):
        """Direct website scraping for major Nigerian newspapers"""
        newspapers = [
            {
                'name': 'Premium Times',
                'url': 'https://www.premiumtimesng.com/',
                'selectors': {
                    'articles': 'article',
                    'title': 'h2 a',
                    'link': 'h2 a',
                    'summary': '.entry-summary',
                    'image': 'img'
                }
            },
            {
                'name': 'Vanguard',
                'url': 'https://www.vanguardngr.com/',
                'selectors': {
                    'articles': '.rtp-latest-news-list li',
                    'title': 'h3 a',
                    'link': 'h3 a',
                    'summary': '.post-excerpt',
                    'image': 'img'
                }
            },
        ]
        
        for paper in newspapers:
            try:
                response = self.session.get(paper['url'], timeout=15)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                selectors = paper['selectors']
                
                articles = soup.select(selectors['articles'])[:5]  # Get 5 articles
                
                for article in articles:
                    try:
                        title_elem = article.select_one(selectors['title'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.text.strip()
                        link = title_elem.get('href', '')
                        
                        if not title or not link:
                            continue
                        
                        # Make link absolute if relative
                        if link.startswith('/'):
                            link = paper['url'].rstrip('/') + link
                        
                        # Get summary
                        summary = ''
                        if selectors['summary']:
                            summary_elem = article.select_one(selectors['summary'])
                            if summary_elem:
                                summary = summary_elem.text.strip()
                        
                        # Get image
                        image_url = ''
                        if selectors['image']:
                            img_elem = article.select_one(selectors['image'])
                            if img_elem and img_elem.get('src'):
                                image_url = img_elem.get('src')
                                if image_url.startswith('/'):
                                    image_url = paper['url'].rstrip('/') + image_url
                        
                        self.articles.append({
                            'title': title,
                            'content': summary[:400] if summary else title,
                            'url': link,
                            'source': paper['name'],
                            'image_url': image_url,
                            'published_at': '',
                            'category': 'News',
                            'method': 'web_scrape'
                        })
                        
                    except Exception as e:
                        logger.error(f"Error parsing article in {paper['name']}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error scraping {paper['name']}: {e}")
                continue
    
    def fetch_reddit_news(self):
        """Fetch Nigeria news from Reddit"""
        try:
            # Reddit Nigeria subreddit
            url = "https://www.reddit.com/r/Nigeria/.json"
            headers = {'User-Agent': 'Ojukaye News Fetcher/1.0'}
            
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for post in data.get('data', {}).get('children', [])[:8]:
                    post_data = post.get('data', {})
                    
                    title = post_data.get('title', '')
                    if not title:
                        continue
                    
                    # Skip if it's a self post without external link
                    url = post_data.get('url', '')
                    if 'reddit.com' in url:
                        continue  # Skip internal Reddit links
                    
                    self.articles.append({
                        'title': title,
                        'content': post_data.get('selftext', '')[:300] or title,
                        'url': url,
                        'source': 'Reddit r/Nigeria',
                        'image_url': post_data.get('thumbnail', ''),
                        'published_at': datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat(),
                        'category': 'Community',
                        'method': 'reddit'
                    })
                    
        except Exception as e:
            logger.error(f"Error fetching Reddit: {e}")
    
    def detect_category(self, title):
        """Detect category based on keywords in title"""
        title_lower = title.lower()
        
        category_keywords = {
            'Politics': ['president', 'senate', 'governor', 'election', 'politic', 'apc', 'pdp', 'minister'],
            'Economy': ['naira', 'dollar', 'economy', 'inflation', 'budget', 'finance', 'stock', 'market'],
            'Sports': ['sport', 'football', 'super eagles', 'premier league', 'champions league', 'athlete'],
            'Technology': ['tech', 'startup', 'digital', 'app', 'software', 'internet', 'phone', 'computer'],
            'Entertainment': ['music', 'movie', 'actor', 'actress', 'celebrity', 'nollywood', 'film'],
            'Crime': ['crime', 'robber', 'kill', 'murder', 'police', 'arrest', 'court'],
            'Education': ['school', 'university', 'student', 'teacher', 'education', 'exam'],
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                return category
        
        return 'News'
    
    def remove_duplicates(self, articles):
        """Remove duplicate articles by URL and title similarity"""
        unique_articles = []
        seen_urls = set()
        seen_titles = set()
        
        for article in articles:
            url = article.get('url', '')
            title = article.get('title', '').lower().strip()
            
            # Skip if no URL or title
            if not url or not title:
                continue
            
            # Check exact URL duplicate
            if url in seen_urls:
                continue
            
            # Check title similarity
            is_similar = False
            for seen_title in seen_titles:
                # Calculate simple similarity
                words1 = set(title.split())
                words2 = set(seen_title.split())
                common = len(words1.intersection(words2))
                similarity = common / max(len(words1), len(words2), 1)
                
                if similarity > 0.6:  # 60% similarity threshold
                    is_similar = True
                    break
            
            if not is_similar:
                seen_urls.add(url)
                seen_titles.add(title)
                unique_articles.append(article)
        
        return unique_articles
    
    def save_articles(self, articles):
        """Save articles to database"""
        print(f"[SAVE_ARTICLES] Starting with {len(articles)} articles")
        
        if not articles:
            print("[SAVE_ARTICLES] No articles to save")
            return 0
        
        # Get or create system user
        try:
            system_user = User.objects.get(username='news_bot')
        except User.DoesNotExist:
            print("[SAVE_ARTICLES] Creating news_bot user...")
            system_user = User.objects.create_user(
                username='news_bot',
                email='news@ojukaye.com',
                password='unusablepassword123',
                first_name='News',
                last_name='Bot',
                is_active=False
            )
        
        saved_count = 0
        current_time = timezone.now()
        
        for i, article in enumerate(articles[:100], 1):  # Increased from 50 to 100
            try:
                title = article.get('title', '').strip()
                url = article.get('url', '')
                
                if not title or not url:
                    print(f"[SAVE_ARTICLES] [{i}] Skipping - no title or URL")
                    continue
                
                print(f"[SAVE_ARTICLES] [{i}] Processing: {title[:50]}...")
                
                # Truncate URL if too long for database
                if len(url) > 1000:
                    print(f"[SAVE_ARTICLES] [{i}] WARNING: URL truncated from {len(url)} to 1000 chars")
                    url = url[:1000]
                
                # Check if already exists by URL
                if Post.objects.filter(external_url=url).exists():
                    print(f"[SAVE_ARTICLES] [{i}] Already exists - skipping")
                    continue
                
                # Get or create category
                category_name = article.get('category', 'News')
                category, created = Category.objects.get_or_create(
                    name=category_name,
                    defaults={
                        'slug': category_name.lower().replace(' ', '-'),
                        'description': f'{category_name} news'
                    }
                )
                if created:
                    print(f"[SAVE_ARTICLES] [{i}] Created category: {category_name}")
                
                # Parse date
                published_str = article.get('published_at')
                published_at = current_time
                
                if published_str:
                    published_at = self.parse_date(published_str)
                
                # Clean content
                content = article.get('content', title)
                import re
                content = re.sub('<[^<]+?>', '', content)  # Remove HTML
                content = re.sub(r'\s+', ' ', content).strip()
                
                # Truncate if needed
                title = title[:200]  # Ensure title fits in 200 chars
                content = content[:1500]  # Limit content length
                
                # Get source and truncate if needed
                source = article.get('source', 'Unknown')[:100]
                
                # Get image URL and truncate
                image_url = article.get('image_url', '')
                if image_url and len(image_url) > 1000:
                    image_url = image_url[:1000]
                
                # Create the post
                post = Post.objects.create(
                    title=title,
                    content=content,
                    post_type='news',
                    category=category,
                    author=system_user,
                    external_source=source,
                    external_url=url,
                    image_url=image_url,
                    published_at=published_at,
                    status='published',
                    is_auto_fetched=True,
                    is_approved=True,  # Auto-approve
                    meta_description=content[:160] if content else title[:160],
                    verification_status='verified'  # Auto-verify fetched news
                )
                
                saved_count += 1
                print(f"[SAVE_ARTICLES] [{i}] ✓ SAVED: {title[:50]}...")
                
            except Exception as e:
                print(f"[SAVE_ARTICLES] [{i}] ✗ ERROR: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"[SAVE_ARTICLES] Complete! Saved {saved_count} articles")
        return saved_count

    def parse_date(self, date_str):
        """Parse various date formats and ensure timezone awareness"""
        if not date_str:
            return timezone.now()
        
        try:
            # Try common RSS date formats
            formats = [
                '%a, %d %b %Y %H:%M:%S %z',
                '%a, %d %b %Y %H:%M:%S %Z',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
            ]
            
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    # Make timezone aware
                    if parsed_date.tzinfo is None:
                        return timezone.make_aware(parsed_date)
                    return parsed_date
                except:
                    continue
            
            # Try parsing timestamp
            if date_str.isdigit():
                parsed_date = datetime.fromtimestamp(int(date_str))
                return timezone.make_aware(parsed_date)
                
        except:
            pass
        
        return timezone.now()