// Main JavaScript for Ojukaye Platform

$(document).ready(function() {
    // Initialize tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();
    
    // Initialize popovers
    $('[data-bs-toggle="popover"]').popover({
        trigger: 'hover',
        placement: 'auto'
    });
    
    // User profile dropdown
    $('#userProfile').click(function(e) {
        e.stopPropagation();
        $(this).find('.dropdown-menu').toggleClass('show');
    });
    
    // Close dropdown when clicking outside
    $(document).click(function() {
        $('.dropdown-menu').removeClass('show');
    });
    
    // Like button functionality
    $('.like-btn').click(function(e) {
        e.preventDefault();
        const btn = $(this);
        const postId = btn.data('post-id');
        
        if (!isAuthenticated()) {
            showQuickLoginModal();
            return;
        }
        
        $.ajax({
            url: `/api/post/${postId}/like/`,
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(data) {
                if (data.success || data.liked !== undefined) {
                    const liked = data.liked;
                    const icon = btn.find('i');
                    const countText = btn.find('span');
                    
                    if (liked) {
                        icon.removeClass('far').addClass('fas');
                        btn.addClass('active');
                        showNotification('Post liked!', 'success');
                    } else {
                        icon.removeClass('fas').addClass('far');
                        btn.removeClass('active');
                        showNotification('Post unliked', 'info');
                    }
                    
                    // Update like count in stats if available
                    const likeCountElement = btn.closest('.post-card').find('.post-stats .stat-item:first-child');
                    if (likeCountElement.length && data.like_count !== undefined) {
                        likeCountElement.text(`❤️ ${data.like_count}`);
                    }
                }
            },
            error: function(xhr, status, error) {
                console.error('Error liking post:', error);
                showNotification('Error liking post. Please try again.', 'error');
            }
        });
    });
    
    // Bookmark button functionality
    $('.bookmark-btn').click(function(e) {
        e.preventDefault();
        const btn = $(this);
        const postId = btn.data('post-id');
        
        if (!isAuthenticated()) {
            showQuickLoginModal();
            return;
        }
        
        $.ajax({
            url: `/api/post/${postId}/bookmark/`,
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(data) {
                if (data.bookmarked !== undefined) {
                    const icon = btn.find('i');
                    
                    if (data.bookmarked) {
                        icon.removeClass('far').addClass('fas');
                        btn.addClass('active');
                        showNotification('Post saved to bookmarks', 'success');
                    } else {
                        icon.removeClass('fas').addClass('far');
                        btn.removeClass('active');
                        showNotification('Post removed from bookmarks', 'info');
                    }
                }
            },
            error: function(xhr, status, error) {
                console.error('Error bookmarking post:', error);
                showNotification('Error saving post. Please try again.', 'error');
            }
        });
    });
    
    // Comment form submission
    $('.comment-form').submit(function(e) {
        e.preventDefault();
        const form = $(this);
        const postId = form.data('post-id');
        const content = form.find('input[name="content"]').val().trim();
        
        if (!content) return;
        
        if (!isAuthenticated()) {
            showQuickLoginModal();
            return;
        }
        
        $.ajax({
            url: `/post/${postId}/comment/`,
            method: 'POST',
            data: {
                content: content,
                csrfmiddlewaretoken: getCSRFToken()
            },
            success: function(data) {
                if (data.success) {
                    form.find('input[name="content"]').val('');
                    form.closest('.quick-comment').addClass('d-none');
                    showNotification('Comment posted successfully!', 'success');
                    
                    // Refresh comments section or update count
                    setTimeout(() => {
                        location.reload();
                    }, 1000);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error posting comment:', error);
                showNotification('Error posting comment. Please try again.', 'error');
            }
        });
    });
    
    // Share button functionality
    $('.share-btn').click(function(e) {
        e.preventDefault();
        const postId = $(this).data('post-id');
        const postUrl = `${window.location.origin}/post/${postId}/`;
        
        if (navigator.share) {
            navigator.share({
                title: 'Check out this post on Ojukaye',
                url: postUrl
            }).catch(console.error);
        } else {
            // Fallback: copy to clipboard
            navigator.clipboard.writeText(postUrl).then(function() {
                showNotification('Link copied to clipboard!', 'success');
            }).catch(function() {
                // Final fallback
                prompt('Copy this link:', postUrl);
            });
        }
    });
    
    // Search functionality
    $('.navbar-search form').submit(function(e) {
        const searchInput = $(this).find('input[name="q"]');
        if (!searchInput.val().trim()) {
            e.preventDefault();
            searchInput.focus();
        }
    });
    
    // Dark mode toggle (if implemented)
    if (localStorage.getItem('darkMode') === 'true') {
        $('body').addClass('dark-mode');
    }
    
    // Notification system
    function checkNotifications() {
        if (isAuthenticated()) {
            $.ajax({
                url: '/api/notifications/count/',
                method: 'GET',
                success: function(data) {
                    if (data.count > 0) {
                        $('.notification-badge').text(data.count).show();
                    } else {
                        $('.notification-badge').hide();
                    }
                }
            });
        }
    }
    
    // Check notifications every minute
    setInterval(checkNotifications, 60000);
    
    // Initial notification check
    checkNotifications();
    
    // Helper Functions
    function isAuthenticated() {
        return document.cookie.includes('sessionid=') || document.cookie.includes('csrftoken=');
    }
    
    function getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    function showNotification(message, type = 'info') {
        // Remove existing notifications
        $('.custom-notification').remove();
        
        const types = {
            'success': { icon: 'check-circle', color: '#28a745' },
            'error': { icon: 'exclamation-circle', color: '#dc3545' },
            'warning': { icon: 'exclamation-triangle', color: '#ffc107' },
            'info': { icon: 'info-circle', color: '#17a2b8' }
        };
        
        const config = types[type] || types.info;
        
        const notification = $(`
            <div class="custom-notification alert alert-dismissible fade show">
                <i class="fas fa-${config.icon} me-2"></i>
                <span>${message}</span>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `);
        
        // Add custom styling
        notification.css({
            'position': 'fixed',
            'top': '80px',
            'right': '20px',
            'z-index': '9999',
            'min-width': '300px',
            'background-color': 'white',
            'color': 'var(--text-dark)',
            'border': `1px solid ${config.color}40`,
            'border-left': `4px solid ${config.color}`,
            'border-radius': '12px',
            'box-shadow': '0 4px 15px var(--shadow-light)',
            'backdrop-filter': 'blur(10px)'
        });
        
        $('body').append(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            notification.alert('close');
        }, 3000);
    }
    
    function showQuickLoginModal() {
        const modal = new bootstrap.Modal(document.getElementById('quickLoginModal'));
        modal.show();
    }
    
    // Banner carousel for all pages
    if ($('.banner-slider').length) {
        $('.banner-slider').slick({
            dots: true,
            infinite: true,
            speed: 500,
            fade: true,
            cssEase: 'linear',
            autoplay: true,
            autoplaySpeed: 5000,
            arrows: true,
            prevArrow: '<button type="button" class="slick-prev"><i class="fas fa-chevron-left"></i></button>',
            nextArrow: '<button type="button" class="slick-next"><i class="fas fa-chevron-right"></i></button>',
            responsive: [
                {
                    breakpoint: 768,
                    settings: {
                        arrows: false
                    }
                }
            ]
        });
    }
    
    // Infinite scroll for posts (if enabled)
    let isLoading = false;
    let nextPage = 2;
    const hasMorePages = $('.pagination').length > 0;
    
    if (hasMorePages) {
        $(window).scroll(function() {
            if ($(window).scrollTop() + $(window).height() > $(document).height() - 500) {
                if (!isLoading && nextPage) {
                    loadMorePosts();
                }
            }
        });
    }
    
    function loadMorePosts() {
        isLoading = true;
        const currentUrl = window.location.pathname;
        const params = new URLSearchParams(window.location.search);
        params.set('page', nextPage);
        
        $.ajax({
            url: currentUrl + '?' + params.toString(),
            method: 'GET',
            beforeSend: function() {
                $('#posts-feed').append('<div class="text-center py-4"><div class="spinner-border text-accent"></div></div>');
            },
            success: function(data) {
                const $newData = $(data).find('.post-card');
                if ($newData.length) {
                    $('.post-card:last').after($newData);
                    nextPage++;
                    // Re-initialize event handlers for new elements
                    initializePostEvents();
                } else {
                    nextPage = null;
                    $('#posts-feed').append('<div class="text-center py-4 text-muted">No more posts to load</div>');
                }
            },
            error: function() {
                showNotification('Error loading more posts', 'error');
            },
            complete: function() {
                isLoading = false;
                $('#posts-feed .spinner-border').remove();
            }
        });
    }

    $(document).ready(function() {
        // Mobile menu toggle
        $('#mobileMenuToggle').click(function() {
            $('#mobileSidebar, #mobileOverlay').addClass('active');
        });
        
        $('#mobileOverlay').click(function() {
            $('#mobileSidebar, #mobileOverlay').removeClass('active');
        });
    });
    
    function initializePostEvents() {
        // Re-initialize all post interaction events
        $('.like-btn, .bookmark-btn, .share-btn, .comment-btn').off('click').on('click', function(e) {
            const btn = $(this);
            if (btn.hasClass('like-btn')) {
                handleLike(btn);
            } else if (btn.hasClass('bookmark-btn')) {
                handleBookmark(btn);
            } else if (btn.hasClass('share-btn')) {
                handleShare(btn);
            } else if (btn.hasClass('comment-btn')) {
                const postId = btn.data('post-id');
                $(`#commentForm-${postId}`).toggleClass('d-none');
            }
            e.preventDefault();
        });
        
        $('.comment-form').off('submit').on('submit', handleCommentSubmit);
    }
    
    // Handle keyboard shortcuts
    $(document).keydown(function(e) {
        // Ctrl/Cmd + K for search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            $('.navbar-search input').focus();
        }
        
        // '/' for search
        if (e.key === '/' && !$(e.target).is('input, textarea')) {
            e.preventDefault();
            $('.navbar-search input').focus();
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            $('.modal').modal('hide');
        }
    });
    
    // Initialize post events on page load
    initializePostEvents();
    
    // Performance optimization: Lazy load images
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.add('loaded');
                    observer.unobserve(img);
                }
            });
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
});