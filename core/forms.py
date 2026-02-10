# core/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import URLValidator, ValidationError
from django.utils import timezone

class RegistrationForm(UserCreationForm):
    ACCOUNT_TYPES = [
        ('individual', 'Individual Account'),
        ('business', 'Business Account'),
    ]
    
    account_type = forms.ChoiceField(
        choices=ACCOUNT_TYPES,
        widget=forms.RadioSelect,
        initial='individual'
    )
    
    # Business fields
    business_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your Business Name'
        })
    )
    business_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'business@example.com'
        })
    )
    business_phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+234 800 000 0000'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'account_type']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Choose a username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your@email.com',
                'required': True
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('account_type')
        
        if account_type == 'business':
            business_name = cleaned_data.get('business_name')
            business_email = cleaned_data.get('business_email')
            
            if not business_name:
                self.add_error('business_name', 'Business name is required for business accounts')
            if not business_email:
                self.add_error('business_email', 'Business email is required for business accounts')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            
            # Import UserProfile here to avoid circular import
            from .models import UserProfile
            
            # Create user profile with account type
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.account_type = self.cleaned_data['account_type']
            
            if self.cleaned_data['account_type'] == 'business':
                profile.business_name = self.cleaned_data.get('business_name', '')
                profile.business_email = self.cleaned_data.get('business_email', '')
                profile.business_phone = self.cleaned_data.get('business_phone', '')
            
            profile.save()
        
        return user

class PostForm(forms.ModelForm):
    POST_TYPE_CHOICES = [
        ('discussion', 'Discussion'),
        ('user_news', 'User News'),
        ('profile_post', 'Profile Post'),
    ]
    
    post_type = forms.ChoiceField(
        choices=POST_TYPE_CHOICES,
        widget=forms.RadioSelect,
        initial='discussion'
    )
    
    class Meta:
        # Import Post model here to avoid circular import
        from .models import Post
        model = Post
        fields = [
            'title', 'content', 'post_type', 'category', 
            'source_url', 'source_name', 'image',
            'allow_comments', 'allow_sharing'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter post title',
                'required': True
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Write your post content...',
                'required': True
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'source_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/news-article'
            }),
            'source_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Source name (e.g., BBC News)'
            }),
            'allow_comments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_sharing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        post_type = cleaned_data.get('post_type')
        source_url = cleaned_data.get('source_url')
        
        if post_type == 'user_news' and not source_url:
            raise forms.ValidationError('Source URL is required for User News posts')
        
        # Validate URL for user news
        if post_type == 'user_news' and source_url:
            try:
                validator = URLValidator()
                validator(source_url)
            except ValidationError:
                raise forms.ValidationError('Please enter a valid URL for the source')
        
        # Profile posts don't need category
        if post_type == 'profile_post':
            cleaned_data['category'] = None
        
        return cleaned_data

class AdSubmissionForm(forms.ModelForm):
    ad_type = forms.ChoiceField(
        # Choices will be set in __init__ to avoid circular import
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        # Import Advertisement model here
        from .models import Advertisement
        model = Advertisement
        fields = [
            'ad_type', 'title', 'content', 'image', 'target_url',
            'budget', 'start_date', 'end_date',
            'target_categories', 'target_locations', 'target_keywords',
            'max_clicks', 'max_impressions'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ad title'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Ad content (optional for banner ads)'
            }),
            'target_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-website.com'
            }),
            'budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1000',
                'step': '100'
            }),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'target_categories': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'target_locations': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Lagos, Abuja, Nigeria (comma separated)'
            }),
            'target_keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'news, politics, sports (comma separated)'
            }),
            'max_clicks': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0 = unlimited'
            }),
            'max_impressions': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0 = unlimited'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set choices after model is loaded
        from .models import Advertisement
        self.fields['ad_type'].choices = Advertisement.AD_TYPES
    
    def clean(self):
        cleaned_data = super().clean()
        budget = cleaned_data.get('budget')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # Get system settings
        from .models import SystemSettings
        try:
            settings = SystemSettings.objects.first()
        except SystemSettings.DoesNotExist:
            settings = SystemSettings.objects.create()
        
        # Budget validation
        if budget and budget < settings.min_ad_budget:
            raise forms.ValidationError(
                f'Minimum budget is ₦{settings.min_ad_budget}'
            )
        
        # Date validation
        if start_date and end_date:
            if start_date >= end_date:
                raise forms.ValidationError('End date must be after start date')
            
            if start_date < timezone.now():
                raise forms.ValidationError('Start date cannot be in the past')
        
        return cleaned_data

class BusinessProfileForm(forms.ModelForm):
    class Meta:
        # Import UserProfile model here
        from .models import UserProfile
        model = UserProfile
        fields = [
            'business_name', 'business_registration', 'business_address',
            'business_phone', 'business_email', 'business_website',
            'profile_pic', 'cover_photo', 'bio'
        ]
        widgets = {
            'business_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Official Business Name'
            }),
            'business_registration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'RC Number or Registration ID'
            }),
            'business_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Business Address'
            }),
            'business_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+234 800 000 0000'
            }),
            'business_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'business@example.com'
            }),
            'business_website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-business.com'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tell us about your business...'
            }),
        }

class GroupForm(forms.ModelForm):
    class Meta:
        # Import Group model here
        from .models import Group
        model = Group
        fields = [
            'name', 'description', 'group_type',
            'cover_image', 'icon',
            'allow_member_posts', 'require_post_approval'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Group Name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your group...'
            }),
            'group_type': forms.Select(attrs={'class': 'form-control'}),
            'allow_member_posts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_post_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class SystemSettingsForm(forms.ModelForm):
    class Meta:
        # Import SystemSettings model here
        from .models import SystemSettings
        model = SystemSettings
        fields = '__all__'
        widgets = {
            'verification_threshold': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'max': '1'
            }),
            'ad_impression_rate': forms.NumberInput(attrs={
                'step': '0.0001',
                'min': '0'
            }),
        }

# Keep existing forms
class CommentForm(forms.ModelForm):
    class Meta:
        from .models import Comment
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add a comment...',
                'required': True
            })
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        from .models import UserProfile
        model = UserProfile
        fields = [
            'bio', 'profile_pic', 'cover_photo', 'location', 'website', 
            'twitter_handle', 'phone', 'date_of_birth', 'occupation', 
            'interests', 'facebook_url', 'instagram_url', 'linkedin_url'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tell us about yourself...'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your location'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://yourwebsite.com'
            }),
            'twitter_handle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '@username'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+234 800 000 0000'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'occupation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your occupation'
            }),
            'interests': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Sports, Technology, Politics, etc.'
            }),
            'facebook_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://facebook.com/username'
            }),
            'instagram_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://instagram.com/username'
            }),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://linkedin.com/in/username'
            }),
        }

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address'
            }),
        }