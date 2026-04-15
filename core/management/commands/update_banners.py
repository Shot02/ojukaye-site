# core/management/commands/update_banners.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q, F
from core.models import Post

class Command(BaseCommand):
    help = 'Update banner posts based on engagement'
    
    def handle(self, *args, **options):
        self.stdout.write('Updating banner posts...')
        
        # Clear old banners
        Post.objects.filter(is_banner=True).update(is_banner=False)
        
        # Get trending posts from last 7 days
        trending_posts = Post.objects.filter(
            status='published',
            post_type__in=['news', 'user_news'],
            published_at__gte=timezone.now() - timedelta(days=7)
        ).annotate(
            like_count=Count('likes'),
            comment_count=Count('comments', filter=Q(comments__is_active=True))
        ).annotate(
            engagement=F('like_count') + F('comment_count') * 2 + F('views') / 100
        ).order_by('-engagement')[:5]
        
        # Mark as banners
        count = 0
        for post in trending_posts:
            post.is_banner = True
            post.banner_priority = 1
            post.banner_expires_at = timezone.now() + timedelta(days=7)
            post.save()
            count += 1
            self.stdout.write(f'  ✓ Marked as banner: {post.title[:50]}...')
        
        # If no trending posts, mark some recent posts
        if count == 0:
            recent_posts = Post.objects.filter(
                status='published',
                post_type__in=['news', 'user_news']
            ).order_by('-published_at')[:5]
            
            for post in recent_posts:
                post.is_banner = True
                post.banner_priority = 1
                post.banner_expires_at = timezone.now() + timedelta(days=7)
                post.save()
                count += 1
                self.stdout.write(f'  ✓ Marked as banner: {post.title[:50]}...')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {count} banner posts'))