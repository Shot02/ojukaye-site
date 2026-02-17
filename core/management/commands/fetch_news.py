# core/management/commands/fetch_news.py

from django.core.management.base import BaseCommand
from django.core.management import call_command
from core.news_fetcher import NewsFetcher
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Orchestrate news fetching from all sources'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test mode (fetch but don\'t save)',
        )
        parser.add_argument(
            '--sources',
            type=str,
            default='all',
            help='Comma-separated sources (newsapi,rss,web)',
        )
        parser.add_argument(
            '--target',
            type=int,
            default=500,
            help='Target number of articles (default: 500)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Days back to fetch (default: 7)',
        )
        parser.add_argument(
            '--threads',
            type=int,
            default=5,
            help='Threads for parallel extraction (default: 5)',
        )
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify articles after fetching',
        )
        parser.add_argument(
            '--fast',
            action='store_true',
            help='Fast mode (skip full content extraction)',
        )
    
    def handle(self, *args, **options):
        test_mode = options['test']
        sources = options['sources'].split(',')
        target = options['target']
        days = options['days']
        threads = options['threads']
        should_verify = options['verify']
        fast_mode = options['fast']
        
        self.stdout.write(self.style.SUCCESS('🚀 Starting Hybrid News Fetch'))
        self.stdout.write(f'📡 Sources: {", ".join(sources)}')
        self.stdout.write(f'🎯 Target: {target} articles')
        self.stdout.write(f'📅 Days: {days}')
        self.stdout.write(f'🔧 Threads: {threads}, Fast Mode: {fast_mode}')
        
        if test_mode:
            self._run_test_mode(sources)
        else:
            self._run_production_mode(sources, target, days, threads, should_verify, fast_mode)
    
    def _run_test_mode(self, sources):
        """Run in test mode (don't save)"""
        self.stdout.write('\n🧪 TEST MODE - Articles found:')
        
        fetcher = NewsFetcher()
        
        if 'newsapi' in sources or 'all' in sources:
            self.stdout.write('\n📰 Testing NewsAPI...')
            fetcher.fetch_newsapi_detailed()
            self._display_results(fetcher.articles, 'NewsAPI')
        
        if 'rss' in sources or 'all' in sources:
            self.stdout.write('\n📡 Testing RSS Feeds...')
            fetcher.articles = []
            fetcher.fetch_rss_feeds_detailed()
            self._display_results(fetcher.articles, 'RSS')
        
        if 'web' in sources or 'all' in sources:
            self.stdout.write('\n🌐 Testing Web Scraping...')
            fetcher.articles = []
            fetcher.fetch_web_scrape_detailed()
            self._display_results(fetcher.articles, 'Web')
    
    def _display_results(self, articles, source_name):
        """Display test results"""
        self.stdout.write(f'  Found {len(articles)} articles from {source_name}')
        for i, article in enumerate(articles[:5], 1):
            self.stdout.write(f'  {i}. {article["title"][:80]}...')
            self.stdout.write(f'     Source: {article["source"]}')
            self.stdout.write(f'     Has Media: {bool(article.get("videos") or article.get("audios"))}')
    
    def _run_production_mode(self, sources, target, days, threads, should_verify, fast_mode):
        """Run in production mode (save to database)"""
        
        if 'newsapi' in sources or 'all' in sources:
            self.stdout.write('\n📰 Fetching from NewsAPI...')
            call_command(
                'fetch_newsapi_bulk',
                days=days,
                limit=min(100, target // 3),
                threads=threads,
                extract_full=not fast_mode,
                verify=False  # We'll verify at the end
            )
        
        if 'rss' in sources or 'all' in sources:
            self.stdout.write('\n📡 Fetching from RSS Feeds...')
            fetcher = NewsFetcher()
            fetcher.fetch_rss_feeds_detailed()
            
            if fast_mode:
                # Skip full content extraction
                saved = fetcher.save_articles(fetcher.articles)
                self.stdout.write(f'  Saved {saved} RSS articles')
            else:
                # Extract full content
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=threads) as executor:
                    # Extract content in parallel
                    pass  # Implementation similar to NewsAPI bulk command
        
        if 'web' in sources or 'all' in sources:
            self.stdout.write('\n🌐 Fetching from Web Scraping...')
            fetcher = NewsFetcher()
            fetcher.fetch_web_scrape_detailed()
            # Similar to RSS handling
        
        # Run verification if requested
        if should_verify:
            self.stdout.write('\n🔎 Running verification on new articles...')
            call_command('verify_news', limit=200, auto_approve=True)