# core/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
import uuid
from django.urls import reverse
from django.db.models import Count, Q

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, default='#3b82f6')
    order = models.IntegerField(default=0)
    
    # Add a cached post count field
    cached_post_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_post_count(self):
        """Get actual post count for this category"""
        # If cached count is 0 or stale, update it
        if self.cached_post_count == 0:
            count = self.post_set.filter(status='published', is_auto_fetched=True).count()
            self.cached_post_count = count
            self.save(update_fields=['cached_post_count'])
        return self.cached_post_count
    
    def update_post_count(self):
        """Update cached post count"""
        self.cached_post_count = self.post_set.filter(status='published').count()
        self.save(update_fields=['cached_post_count'])

class SystemSettings(models.Model):
    """System-wide settings controlled by admin"""
    auto_verify_news = models.BooleanField(default=True)
    auto_delete_fake_news = models.BooleanField(default=False)
    verification_threshold = models.FloatField(default=0.7, validators=[MinValueValidator(0), MaxValueValidator(1)])
    enable_guest_access = models.BooleanField(default=True)
    max_posts_per_day = models.IntegerField(default=10)
    max_ads_per_business = models.IntegerField(default=5)
    banner_rotation_interval = models.IntegerField(default=30)  # seconds
    trending_calculation_interval = models.IntegerField(default=6)  # hours
    
    # Ad settings
    ad_approval_required = models.BooleanField(default=True)
    min_ad_budget = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    ad_impression_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0.001)  # per impression
    
    # Group settings
    allow_group_creation = models.BooleanField(default=True)
    max_groups_per_user = models.IntegerField(default=5)
    min_members_for_public_group = models.IntegerField(default=10)
    
    class Meta:
        verbose_name_plural = "System Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SystemSettings.objects.exists():
            return
        super().save(*args, **kwargs)
    
    def __str__(self):
        return "System Settings"

class Advertisement(models.Model):
    AD_TYPES = [
        ('banner', 'Banner Ad'),
        ('sponsored_post', 'Sponsored Post'),
        ('sidebar', 'Sidebar Ad'),
        ('in_feed', 'In-Feed Ad'),
    ]
    
    AD_STATUS = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    ]
    
    business = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ads')
    ad_type = models.CharField(max_length=20, choices=AD_TYPES, default='banner')
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to='ads/', blank=True, null=True)
    image_url = models.URLField(max_length=1000, blank=True)
    target_url = models.URLField(max_length=1000)
    
    # Budget & Duration
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    
    # Targeting
    target_categories = models.ManyToManyField('Category', blank=True)
    target_locations = models.CharField(max_length=500, blank=True)
    target_keywords = models.CharField(max_length=500, blank=True)
    
    # Status & Approval
    status = models.CharField(max_length=20, choices=AD_STATUS, default='pending')
    is_active = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_ads')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Performance tracking
    max_clicks = models.IntegerField(default=0)  # 0 = unlimited
    max_impressions = models.IntegerField(default=0)  # 0 = unlimited
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.business.username}"
    
    @property
    def is_live(self):
        now = timezone.now()
        return (self.status == 'active' and 
                self.is_active and
                self.start_date <= now <= self.end_date and
                (self.max_clicks == 0 or self.clicks < self.max_clicks) and
                (self.max_impressions == 0 or self.impressions < self.max_impressions))
    
    def remaining_budget(self):
        return self.budget - self.spent
    
    def days_remaining(self):
        if self.end_date < timezone.now():
            return 0
        return (self.end_date - timezone.now()).days

class Post(models.Model):
    POST_TYPES = [
        ('discussion', 'Discussion'),
        ('business', 'Business'),
        ('user_news', 'User News'),
        ('news', 'Auto-Fetched News'),
        ('profile_post', 'Profile Post'),
        ('sponsored', 'Sponsored Post'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('featured', 'Featured'),
        ('archived', 'Archived'),
    ]
    
    title = models.CharField(max_length=500)
    content = models.TextField()
    post_type = models.CharField(max_length=20, choices=POST_TYPES, default='discussion')
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    
    # For user-submitted news
    source_url = models.URLField(max_length=1000, blank=True, null=True)
    source_name = models.CharField(max_length=200, blank=True)
    
    # For external news
    external_source = models.CharField(max_length=200, blank=True)
    external_url =  models.URLField(max_length=1000, blank=True) 
    external_id = models.CharField(max_length=200, blank=True, unique=True)
    is_auto_fetched = models.BooleanField(default=False)  # New field to identify auto-fetched news
    
    # New fields
    is_sponsored = models.BooleanField(default=False)
    is_banner = models.BooleanField(default=False)
    profile_only = models.BooleanField(default=False)  # Only visible on profile
    advertisement = models.ForeignKey(Advertisement, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    
    # Add banner-specific fields
    banner_expires_at = models.DateTimeField(null=True, blank=True)
    banner_priority = models.IntegerField(default=0)  # Higher number = higher priority
    banner_clicks = models.PositiveIntegerField(default=0)
    banner_impressions = models.PositiveIntegerField(default=0)
    
    # Add group relation
    group = models.ForeignKey('Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='group_posts')
    
    # Add profile post visibility
    allow_comments = models.BooleanField(default=True)
    allow_sharing = models.BooleanField(default=True)
    
    # Stats
    views = models.PositiveIntegerField(default=0)
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)
    shares = models.PositiveIntegerField(default=0)
    bookmarks = models.ManyToManyField(User, related_name='bookmarked_posts', blank=True)
    reposts = models.PositiveIntegerField(default=0)
    
    # Social media features
    repost_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0, db_column='comment_count')# Cache comment count
    share_count = models.PositiveIntegerField(default=0)
    
    # For trending algorithm
    engagement_score = models.FloatField(default=0.0)
    last_engagement_update = models.DateTimeField(auto_now=True)

    # For news verification
    is_verified = models.BooleanField(default=False)  # Auto-verified by detector
    is_approved = models.BooleanField(default=False)  # Manually approved by admin
    verification_score = models.FloatField(default=0.0)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('fake', 'Fake'),
            ('checking', 'Checking'),
        ],
        default='pending'
    )
    verification_details = models.JSONField(default=dict, blank=True)
    
    def update_engagement_score(self):
        """Update engagement score for trending"""
        # Update comments count
        self.comments_count = self.comments.filter(is_active=True).count()
        
        # Calculate engagement score
        like_weight = 1
        comment_weight = 3  # Comments are more valuable than likes
        repost_weight = 5   # Reposts are very valuable
        view_weight = 0.01  # Views have less weight
        
        self.engagement_score = (
            self.likes.count() * like_weight +
            self.comments_count * comment_weight +
            self.reposts * repost_weight +
            self.views * view_weight
        )
        self.last_engagement_update = timezone.now()
        
        # Save updated fields
        self.save(update_fields=['engagement_score', 'last_engagement_update', 'comments_count'])
    
    @property
    def comment_count(self):
        """Property accessor for backward compatibility"""
        return self.comments_count

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(default=timezone.now)
    
    # Media
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    image = models.ImageField(upload_to='post_images/', blank=True, null=True)
    
    # SEO
    meta_description = models.TextField(blank=True)
    keywords = models.CharField(max_length=500, blank=True)
    
    # For home page display
    is_featured = models.BooleanField(default=False, help_text="Display on home page")
    is_trending = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['status']),
            models.Index(fields=['post_type']),
            models.Index(fields=['category']),
            models.Index(fields=['is_auto_fetched']),
            models.Index(fields=['is_sponsored']),
            models.Index(fields=['profile_only']),
        ]
    
    def __str__(self):
        return self.title[:100]
    
    def like_count(self):
        return self.likes.count()
    
    def comment_count(self):
        return self.comments.filter(is_active=True).count()
    
    def bookmark_count(self):
        return self.bookmarks.count()
    
    def save(self, *args, **kwargs):
        # Auto-detect if post is auto-fetched
        if self.author and self.author.username == 'news_bot':
            self.is_auto_fetched = True
            self.post_type = 'news'
        
        # Also auto-detect by external fields
        if self.external_id or self.external_url or self.external_source:
            self.is_auto_fetched = True
            self.post_type = 'news'
        
        # Auto-set profile_only for profile posts
        if self.post_type == 'profile_post':
            self.profile_only = True
            self.category = None  # Profile posts don't have categories
            
        # Auto-set is_sponsored for sponsored posts
        if self.post_type == 'sponsored' and self.advertisement:
            self.is_sponsored = True
            
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('post_detail', args=[str(self.id)])

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    likes = models.ManyToManyField(User, related_name='liked_comments', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title[:50]}"
    
    def like_count(self):
        return self.likes.count()

class UserProfile(models.Model):
    ACCOUNT_TYPES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('group', 'Group Account'),
        ('admin', 'Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    cover_photo = models.ImageField(upload_to='cover_photos/', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(max_length=1000, blank=True)
    twitter_handle = models.CharField(max_length=50, blank=True)
    
    # Additional fields for profile
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    interests = models.TextField(blank=True, help_text="Comma separated list of interests")
    
    # Social media links
    facebook_url = models.URLField(max_length=1000, blank=True)
    instagram_url = models.URLField(max_length=1000, blank=True)
    linkedin_url = models.URLField(max_length=1000, blank=True)
    
    # Account type and business fields
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='individual')
    is_verified_business = models.BooleanField(default=False)
    ad_credits = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Business-specific fields
    business_name = models.CharField(max_length=200, blank=True)
    business_registration = models.CharField(max_length=100, blank=True)
    business_address = models.TextField(blank=True)
    business_phone = models.CharField(max_length=20, blank=True)
    business_email = models.EmailField(blank=True)
    business_website = models.URLField(max_length=1000, blank=True)
    
    # Business verification
    business_verified_at = models.DateTimeField(null=True, blank=True)
    business_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_businesses')
    
    # Ad preferences
    receive_promo_emails = models.BooleanField(default=True)
    ad_notifications = models.BooleanField(default=True)
    
    # Group account fields
    is_group_account = models.BooleanField(default=False)
    group = models.ForeignKey('Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='profile')
    
    # Stats
    total_posts = models.PositiveIntegerField(default=0)
    total_comments = models.PositiveIntegerField(default=0)
    total_likes_received = models.PositiveIntegerField(default=0)
    followers_count = models.PositiveIntegerField(default=0)
    following_count = models.PositiveIntegerField(default=0)
    
    # Settings
    email_notifications = models.BooleanField(default=True)
    show_online_status = models.BooleanField(default=True)
    privacy_level = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('private', 'Private'),
            ('friends_only', 'Friends Only')
        ],
        default='public'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        if self.account_type == 'business' and self.business_name:
            return f"{self.business_name} ({self.user.username})"
        return f"{self.user.username}'s Profile"
    
    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
    
    def update_stats(self):
        self.total_posts = self.user.posts.count()
        self.total_comments = self.user.comment_set.count()
        self.total_likes_received = self.user.posts.aggregate(
            total_likes=models.Sum('likes__count')
        )['total_likes'] or 0
        self.save()
    
    def get_interests_list(self):
        if self.interests:
            return [interest.strip() for interest in self.interests.split(',')]
        return []
    
    def can_submit_ads(self):
        """Check if user can submit ads"""
        if self.account_type != 'business':
            return False
        if not self.is_verified_business:
            return False
        return True
    
    def get_remaining_ad_credits(self):
        """Get remaining ad credits"""
        active_ads = Advertisement.objects.filter(
            business=self.user,
            status__in=['active', 'approved'],
            is_active=True
        )
        total_budget = sum(ad.budget for ad in active_ads)
        return self.ad_credits - total_budget

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['follower', 'following']
    
    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"

class UserActivity(models.Model):
    ACTIVITY_TYPES = [
        ('post_created', 'Post Created'),
        ('comment_created', 'Comment Created'),
        ('post_liked', 'Post Liked'),
        ('post_shared', 'Post Shared'),
        ('post_saved', 'Post Saved'),
        ('post_reposted', 'Post Reposted'),
        ('profile_updated', 'Profile Updated'),
        ('followed_user', 'Followed User'),
        ('ad_submitted', 'Ad Submitted'),
        ('group_created', 'Group Created'),
        ('group_joined', 'Group Joined'),
        ('ad_approved', 'Ad Approved'),
        ('ad_rejected', 'Ad Rejected'),
        ('business_verified', 'Business Verified'),
        ('group_post_created', 'Group Post Created'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)  # Increased from 50 to appropriate length
    post = models.ForeignKey('Post', on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey('Comment', on_delete=models.CASCADE, null=True, blank=True)
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='target_activities')
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'User Activities'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('like', 'Like'),
        ('comment', 'Comment'),
        ('follow', 'Follow'),
        ('mention', 'Mention'),
        ('post', 'New Post'),
        ('reply', 'Reply'),
        ('ad_approval', 'Ad Approval'),
        ('business_verification', 'Business Verification'),
        ('group_invite', 'Group Invite'),
        ('group_post_approved', 'Group Post Approved'),
        ('group_post_rejected', 'Group Post Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='sent_notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)  # Increased from 20 to 30
    message = models.CharField(max_length=500)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} notification for {self.user.username}"

class Repost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reposts')
    original_post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='repost_instances')
    content = models.TextField(blank=True, help_text="Optional comment when reposting")
    created_at = models.DateTimeField(auto_now_add=True)
    reposts = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'original_post']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} reposted {self.original_post.title}"

class Group(models.Model):
    GROUP_TYPES = [
        ('public', 'Public - Anyone can join'),
        ('private', 'Private - Approval required'),
        ('secret', 'Secret - Invitation only'),
    ]
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    group_type = models.CharField(max_length=20, choices=GROUP_TYPES, default='public')
    
    # Ownership & Moderation
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    admins = models.ManyToManyField(User, related_name='administered_groups', blank=True)
    moderators = models.ManyToManyField(User, related_name='moderated_groups', blank=True)
    
    # Settings
    allow_member_posts = models.BooleanField(default=True)
    require_post_approval = models.BooleanField(default=False)
    
    # Media
    cover_image = models.ImageField(upload_to='groups/covers/', blank=True, null=True)
    icon = models.ImageField(upload_to='groups/icons/', blank=True, null=True)
    
    # Stats
    member_count = models.PositiveIntegerField(default=0)
    post_count = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class GroupMember(models.Model):
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('moderator', 'Moderator'),
        ('admin', 'Admin'),
    ]
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_banned = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['group', 'user']
    
    def __str__(self):
        return f"{self.user.username} in {self.group.name}"

class GroupPost(models.Model):
    """Posts within groups (separate from main feed)"""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='group_posts')
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['group', 'post']
    
    def __str__(self):
        return f"{self.post.title} in {self.group.name}"

class AdAnalytics(models.Model):
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField(default=timezone.now)
    
    # Metrics
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Performance metrics
    ctr = models.FloatField(default=0)  # Click-through rate
    cpc = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # Cost per click
    
    class Meta:
        unique_together = ['advertisement', 'date']
        verbose_name_plural = "Ad Analytics"
    
    def update_metrics(self):
        """Update derived metrics"""
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        if self.clicks > 0:
            self.cpc = self.cost / self.clicks
        self.save()