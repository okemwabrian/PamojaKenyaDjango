from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.db import models, transaction
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from .models import MembershipApplication, Payment, Claim, Share, ContactMessage, UserProfile, ShareDeduction, Notification, Meeting, Announcement, Message

@login_required
def home(request):
    latest_announcements = Announcement.objects.filter(is_active=True).order_by('-created_at')[:3]
    upcoming_meetings = Meeting.objects.filter(is_active=True, date__gte=timezone.now().date()).order_by('date', 'time')[:3]
    
    context = {
        'latest_announcements': latest_announcements,
        'upcoming_meetings': upcoming_meetings,
    }
    return render(request, 'main/home.html', context)

@login_required
def about(request):
    return render(request, 'main/about.html')

@login_required
def membership(request):
    return render(request, 'main/membership.html')

@login_required
def announcements(request):
    announcements = Announcement.objects.filter(is_active=True).order_by('-created_at')
    upcoming_meetings = Meeting.objects.filter(is_active=True, date__gte=timezone.now().date()).order_by('date', 'time')[:5]
    return render(request, 'main/announcements.html', {
        'announcements': announcements,
        'upcoming_meetings': upcoming_meetings
    })

@login_required
def contact(request):
    if request.method == 'POST':
        # Create contact message
        contact_msg = ContactMessage.objects.create(
            user=request.user,
            name=request.POST.get('name') or f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            email=request.POST.get('email') or request.user.email,
            phone=request.POST.get('phone', ''),
            subject=request.POST.get('subject'),
            message=request.POST.get('message')
        )
        
        # Send email notification
        send_mail(
            f'Contact Message: {contact_msg.subject}',
            f'From: {contact_msg.name}\nEmail: {contact_msg.email}\nPhone: {contact_msg.phone}\n\nMessage:\n{contact_msg.message}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
        
        messages.success(request, 'Thank you! Your message has been sent successfully.')
        return redirect('contact')
    
    # Pre-fill form if user is authenticated
    form_data = {
        'name': f"{request.user.first_name} {request.user.last_name}".strip(),
        'email': request.user.email
    }
    
    return render(request, 'main/contact.html', {'form': form_data})

def login_view(request):
    # Redirect if already logged in
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                auth_login(request, user)
                messages.success(request, 'Welcome! Login successful.')
                if user.is_staff:
                    return redirect('admin_dashboard')
                return redirect('user_dashboard')
            else:
                messages.error(request, 'Your account is not activated yet. Please contact admin.')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    
    return render(request, 'main/login.html')

def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request, 'main/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return render(request, 'main/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return render(request, 'main/register.html')
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=False  # Require admin approval
        )
        
        # Create user profile
        UserProfile.objects.create(
            user=user,
            status='registered'
        )
        
        # Send notification to admin
        try:
            admin_users = User.objects.filter(is_staff=True)
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    notification_type='general',
                    title='New User Registration',
                    message=f'New user {first_name} {last_name} ({username}) has registered and needs approval.'
                )
            
            send_mail(
                'New User Registration - Approval Required',
                f'A new user has registered:\n\nName: {first_name} {last_name}\nUsername: {username}\nEmail: {email}\n\nPlease login to the admin dashboard to approve this user.',
                settings.DEFAULT_FROM_EMAIL,
                [settings.DEFAULT_FROM_EMAIL],
                fail_silently=True,
            )
        except:
            pass
        
        messages.success(request, 'Registration successful! Please wait for admin approval. You will receive an email once your account is activated.')
        return redirect('login')
    
    return render(request, 'main/register.html')

@login_required
def user_dashboard(request):
    # Get user's data from database
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    applications = MembershipApplication.objects.filter(user=request.user)
    payments = Payment.objects.filter(user=request.user)
    claims = Claim.objects.filter(user=request.user)
    shares = Share.objects.filter(user=request.user)
    
    # Calculate totals and update profile
    total_shares = shares.filter(status='approved').aggregate(total=models.Sum('shares_purchased'))['total'] or 0
    profile.shares_owned = total_shares
    
    # Check activation/deactivation status
    if profile.shares_owned <= 20:
        if not profile.is_deactivated:
            profile.is_deactivated = True
            profile.status = 'inactive'
            
            # Send low shares email
            send_mail(
                'Account Deactivated - Low Shares Balance',
                f'Dear {request.user.first_name},\n\nYour account has been deactivated because your shares balance ({profile.shares_owned}) is below the minimum required (20 shares).\n\nPlease purchase more shares to reactivate your account.\n\nThank you.',
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email],
                fail_silently=True,
            )
            
            # Create notification
            Notification.objects.create(
                user=request.user,
                notification_type='shares_low',
                title='Account Deactivated - Low Shares',
                message=f'Your account has been deactivated. Current shares: {profile.shares_owned}. Minimum required: 20 shares.'
            )
    else:
        # Reactivate if shares are sufficient
        if profile.is_deactivated:
            profile.is_deactivated = False
            profile.status = 'active'
            
            # Clear old deactivation notifications
            Notification.objects.filter(
                user=request.user, 
                notification_type='shares_low', 
                is_read=False
            ).update(is_read=True)
    
    profile.save()
    
    pending_claims = claims.filter(status='pending').count()
    pending_payments = payments.filter(status='pending').count()
    membership_status = applications.filter(status='approved').first()
    
    # Get notifications (exclude deactivation notifications for active users)
    notifications = Notification.objects.filter(user=request.user, is_read=False)
    if not profile.is_deactivated:
        notifications = notifications.exclude(notification_type='shares_low')
    notifications = notifications.order_by('-created_at')[:5]
    
    context = {
        'membership_status': membership_status.application_type if membership_status else 'None',
        'shares_owned': total_shares,
        'pending_claims': pending_claims,
        'pending_payments': pending_payments,
        'recent_applications': applications.order_by('-created_at')[:3],
        'recent_payments': payments.order_by('-created_at')[:3],
        'recent_claims': claims.order_by('-created_at')[:3],
        'recent_shares': shares.order_by('-created_at')[:3],
        'profile': profile,
        'notifications': notifications,
        'shares_color': profile.get_shares_color(),
    }
    return render(request, 'main/user_dashboard.html', context)

@login_required
def payments(request):
    if request.method == 'POST':
        # Create payment record
        payment = Payment.objects.create(
            user=request.user,
            payment_type=request.POST.get('payment_type'),
            amount=request.POST.get('amount'),
            payment_method=request.POST.get('payment_method'),
            transaction_id=request.POST.get('transaction_id', ''),
            description=request.POST.get('description', ''),
            payment_proof=request.FILES.get('payment_proof')
        )
        
        # Send email notification
        send_mail(
            'New Payment Submission',
            f'New payment from {request.user.username} - ${payment.amount}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
        
        messages.success(request, 'Payment submitted successfully! Admin will review and approve.')
        return redirect('payments')
    
    # Get user's payments
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'main/payments.html', {'payments': payments})

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('user_dashboard')
    
    # Get admin dashboard data
    total_applications = MembershipApplication.objects.count()
    total_payments = Payment.objects.count()
    total_claims = Claim.objects.count()
    
    # Calculate total shares owned by all members (from approved share purchases)
    total_shares_owned = Share.objects.filter(status='approved').aggregate(
        total=models.Sum('shares_purchased'))['total'] or 0
    
    unread_messages = ContactMessage.objects.filter(is_read=False).count()
    pending_users = User.objects.filter(is_active=False, is_staff=False).count()
    
    pending_applications = MembershipApplication.objects.filter(status='pending').order_by('-created_at')[:5]
    pending_payments = Payment.objects.filter(status='pending').order_by('-created_at')[:5]
    pending_claims = Claim.objects.filter(status='pending').order_by('-created_at')[:5]
    pending_shares = Share.objects.filter(status='pending').order_by('-created_at')[:5]
    recent_messages = ContactMessage.objects.order_by('-created_at')[:5]
    
    context = {
        'total_applications': total_applications,
        'total_payments': total_payments,
        'total_claims': total_claims,
        'total_shares': total_shares_owned,  # Now shows actual shares owned by members
        'unread_messages': unread_messages,
        'pending_users': pending_users,
        'pending_applications': pending_applications,
        'pending_payments': pending_payments,
        'pending_claims': pending_claims,
        'pending_shares': pending_shares,
        'recent_messages': recent_messages,
    }
    return render(request, 'main/admin_dashboard.html', context)

@login_required
def meetings(request):
    meetings = Meeting.objects.filter(is_active=True).order_by('date', 'time')
    return render(request, 'main/meetings.html', {'meetings': meetings})

def claims(request):
    return render(request, 'main/claims.html')

@login_required
def shares(request):
    if request.method == 'POST':
        # Create share purchase record
        shares_count = int(request.POST.get('shares', 0))
        share = Share.objects.create(
            user=request.user,
            shares_purchased=shares_count,
            amount=shares_count * 20,  # $20 per share
            payment_method=request.POST.get('paymentMethod'),
            transaction_id=request.POST.get('transactionId', ''),
            notes=request.POST.get('comments', ''),
            payment_proof=request.FILES.get('paymentProof')
        )
        
        # Send email notification
        send_mail(
            'New Share Purchase',
            f'New share purchase from {request.user.username} - {shares_count} shares',
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
        
        messages.success(request, 'Share purchase submitted successfully!')
        return redirect('shares')
    
    # Get user's shares and check status
    shares = Share.objects.filter(user=request.user).order_by('-created_at')
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Update shares count from approved purchases
    approved_shares = Share.objects.filter(user=request.user, status='approved').aggregate(
        total=models.Sum('shares_purchased'))['total'] or 0
    profile.shares_owned = approved_shares
    
    # Check activation/deactivation status
    if profile.shares_owned <= 20:
        if not profile.is_deactivated:
            profile.is_deactivated = True
            profile.status = 'inactive'
            
            # Send low shares email
            send_mail(
                'Account Deactivated - Low Shares Balance',
                f'Dear {request.user.first_name},\n\nYour account has been deactivated because your shares balance ({profile.shares_owned}) is below the minimum required (20 shares).\n\nPlease purchase more shares to reactivate your account.\n\nThank you.',
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email],
                fail_silently=True,
            )
            
            # Create notification
            Notification.objects.create(
                user=request.user,
                notification_type='shares_low',
                title='Account Deactivated - Low Shares',
                message=f'Your account has been deactivated. Current shares: {profile.shares_owned}. Minimum required: 20 shares.'
            )
    else:
        # Reactivate if shares are sufficient
        if profile.is_deactivated:
            profile.is_deactivated = False
            profile.status = 'active'
            
            # Clear old deactivation notifications
            Notification.objects.filter(
                user=request.user, 
                notification_type='shares_low', 
                is_read=False
            ).update(is_read=True)
    
    profile.save()
    
    return render(request, 'main/shares.html', {
        'shares': shares, 
        'profile': profile,
        'shares_color': profile.get_shares_color()
    })

@login_required
def claims(request):
    if request.method == 'POST':
        # Create claim record
        claim = Claim.objects.create(
            user=request.user,
            claim_type=request.POST.get('claim_type'),
            member_name=request.POST.get('member_name'),
            relationship=request.POST.get('relationship'),
            incident_date=request.POST.get('incident_date'),
            amount_requested=request.POST.get('amount_requested'),
            description=request.POST.get('description'),
            supporting_documents=request.FILES.get('supporting_documents')
        )
        
        # Send email notification to admin
        send_mail(
            'New Claim Submission',
            f'New claim from {request.user.username}\nType: {claim.claim_type}\nAmount: ${claim.amount_requested}\nMember: {claim.member_name}\nDescription: {claim.description}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
        
        messages.success(request, 'Claim submitted successfully!')
        return redirect('claims')
    
    # Get user's claims
    claims = Claim.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'main/claims.html', {'claims': claims})

@login_required
def single_application(request):
    if request.method == 'POST':
        # Create membership application
        application = MembershipApplication.objects.create(
            user=request.user,
            application_type='single',
            first_name=request.POST.get('first_name'),
            middle_name=request.POST.get('middle_name', ''),
            last_name=request.POST.get('last_name'),
            email=request.POST.get('email'),
            address=request.POST.get('address'),
            phone_main=request.POST.get('phone_main'),
            minnesota_id=request.FILES.get('minnesota_id'),
            spouse=request.POST.get('spouse', ''),
            spouse_phone=request.POST.get('spouse_phone', ''),
            authorized_rep=request.POST.get('authorized_rep', ''),
            child_1=request.POST.get('child_1', ''),
            child_2=request.POST.get('child_2', ''),
            child_3=request.POST.get('child_3', ''),
            child_4=request.POST.get('child_4', ''),
            child_5=request.POST.get('child_5', ''),
            parent_1=request.POST.get('parent_1', ''),
            parent_2=request.POST.get('parent_2', ''),
            sibling_1=request.POST.get('sibling_1', ''),
            sibling_2=request.POST.get('sibling_2', '')
        )
        
        # Send email notification
        send_mail(
            'New Single Membership Application',
            f'New application from {application.first_name} {application.last_name}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
        
        messages.success(request, 'Application submitted successfully! Please proceed to payment ($200).')
        return redirect('payments')
    return render(request, 'main/single_application.html')



@login_required
def profile(request):
    if request.method == 'POST':
        # Update user profile
        request.user.first_name = request.POST.get('first_name')
        request.user.last_name = request.POST.get('last_name')
        request.user.email = request.POST.get('email')
        request.user.save()
        
        # Handle additional profile fields (create profile model if needed)
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    # Mock profile data - replace with actual profile model
    profile_data = {
        'phone': '',
        'address': '',
        'city': '',
        'state': '',
        'zip_code': '',
        'emergency_contact_name': '',
        'emergency_contact_phone': ''
    }
    
    return render(request, 'main/profile.html', {'profile': profile_data})

@login_required
def upgrade(request):
    if request.method == 'POST':
        # Handle upgrade request
        messages.success(request, 'Upgrade request submitted successfully! We will contact you for payment processing.')
        return redirect('upgrade')
    return render(request, 'main/upgrade.html')



@login_required
def deduct_all_shares(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        shares_to_deduct = int(request.POST.get('shares_to_deduct', 0))
        
        with transaction.atomic():
            # Get all users with shares
            profiles = UserProfile.objects.all()
            total_remaining = 0
            
            for profile in profiles:
                # Recalculate current shares from approved Share records
                current_shares = Share.objects.filter(
                    user=profile.user, status='approved'
                ).aggregate(total=models.Sum('shares_purchased'))['total'] or 0
                
                # Deduct shares
                new_shares = max(0, current_shares - shares_to_deduct)
                profile.shares_owned = new_shares
                
                # Check if user should be deactivated
                if profile.shares_owned <= 20:
                    profile.is_deactivated = True
                    profile.status = 'inactive'
                
                profile.save()
                total_remaining += profile.shares_owned
                
                # Send email to user
                send_mail(
                    'Shares Deducted from Your Account',
                    f'Dear {profile.user.first_name},\n\nShares have been deducted from your account.\nReason: {reason}\nShares deducted: {shares_to_deduct}\nRemaining shares: {profile.shares_owned}\nTotal company shares remaining: {total_remaining}\n\nThank you.',
                    settings.DEFAULT_FROM_EMAIL,
                    [profile.user.email],
                    fail_silently=True,
                )
                
                # Create notification
                Notification.objects.create(
                    user=profile.user,
                    notification_type='shares_deducted',
                    title='Shares Deducted',
                    message=f'Reason: {reason}. Deducted: {shares_to_deduct} shares. Remaining: {profile.shares_owned} shares.'
                )
            
            # Record the deduction
            ShareDeduction.objects.create(
                reason=reason,
                shares_deducted=shares_to_deduct,
                total_remaining_shares=total_remaining,
                created_by=request.user
            )
        
        messages.success(request, f'Successfully deducted {shares_to_deduct} shares from all users.')
        return redirect('admin_dashboard')
    
    return render(request, 'main/deduct_shares.html')

@login_required
def manage_users(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    status_filter = request.GET.get('status', 'all')
    
    # Get all non-staff users and ensure they have profiles
    all_users = User.objects.filter(is_staff=False)
    
    # Create profiles for users who don't have them
    for user in all_users:
        profile, created = UserProfile.objects.get_or_create(
            user=user, 
            defaults={
                'status': 'registered' if user.is_active else 'registered',
                'shares_owned': 0
            }
        )
    
    # Get all profiles for non-staff users
    profiles = UserProfile.objects.select_related('user').filter(user__is_staff=False).order_by('-user__date_joined')
    
    # Apply filters
    if status_filter == 'pending':
        profiles = profiles.filter(user__is_active=False)
    elif status_filter == 'active':
        profiles = profiles.filter(user__is_active=True)
    elif status_filter == 'inactive':
        profiles = profiles.filter(is_deactivated=True)
    
    context = {
        'profiles': profiles,
        'status_filter': status_filter,
        'status_choices': [('all', 'All'), ('pending', 'Pending Approval'), ('active', 'Active'), ('inactive', 'Inactive')]
    }
    return render(request, 'main/manage_users.html', context)

@login_required
def activate_user(request, user_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        profile = UserProfile.objects.get(user_id=user_id)
        profile.is_deactivated = False
        profile.status = 'active'
        profile.save()
        
        # Activate user account
        profile.user.is_active = True
        profile.user.save()
        
        # Send activation email to user
        try:
            send_mail(
                'Account Activated - Pamoja Kenya MN',
                f'Dear {profile.user.first_name},\n\nYour account has been activated! You can now login and access all services.\n\nWelcome to Pamoja Kenya MN!\n\nLogin at: http://localhost:8000/login/',
                settings.DEFAULT_FROM_EMAIL,
                [profile.user.email],
                fail_silently=True,
            )
            
            # Create notification for user
            Notification.objects.create(
                user=profile.user,
                notification_type='general',
                title='Account Activated',
                message='Your account has been activated! You can now access all services.'
            )
        except:
            pass
        
        messages.success(request, f'User {profile.user.username} activated successfully.')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User not found.')
    
    return redirect('manage_users')

@login_required
def user_details(request, user_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    try:
        profile = UserProfile.objects.get(user_id=user_id)
        applications = MembershipApplication.objects.filter(user_id=user_id)
        payments = Payment.objects.filter(user_id=user_id)
        claims = Claim.objects.filter(user_id=user_id)
        shares = Share.objects.filter(user_id=user_id)
        
        # Get membership type from approved application
        approved_app = applications.filter(status='approved').first()
        membership_type = approved_app.get_application_type_display() if approved_app else 'None'
        
        context = {
            'profile': profile,
            'applications': applications,
            'payments': payments,
            'claims': claims,
            'shares': shares,
            'membership_type': membership_type
        }
        return render(request, 'main/user_details.html', context)
    except UserProfile.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('manage_users')

@login_required
def admin_meetings(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        Meeting.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description', ''),
            date=request.POST.get('date'),
            time=request.POST.get('time'),
            location=request.POST.get('location'),
            meeting_type=request.POST.get('meeting_type'),
            max_attendees=request.POST.get('max_attendees') or None,
            is_active=request.POST.get('is_active') == 'on',
            created_by=request.user
        )
        messages.success(request, 'Meeting created successfully!')
        return redirect('admin_meetings')
    
    meetings = Meeting.objects.all().order_by('-created_at')
    return render(request, 'main/admin_meetings.html', {'meetings': meetings})

@login_required
def admin_announcements(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        Announcement.objects.create(
            title=request.POST.get('title'),
            content=request.POST.get('content'),
            announcement_type=request.POST.get('announcement_type'),
            is_active=request.POST.get('is_active') == 'on',
            created_by=request.user
        )
        messages.success(request, 'Announcement created successfully!')
        return redirect('admin_announcements')
    
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'main/admin_announcements.html', {'announcements': announcements})

@login_required
def edit_meeting(request, meeting_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    meeting = Meeting.objects.get(id=meeting_id)
    if request.method == 'POST':
        meeting.title = request.POST.get('title')
        meeting.description = request.POST.get('description', '')
        meeting.date = request.POST.get('date')
        meeting.time = request.POST.get('time')
        meeting.location = request.POST.get('location')
        meeting.meeting_type = request.POST.get('meeting_type')
        meeting.max_attendees = request.POST.get('max_attendees') or None
        meeting.is_active = request.POST.get('is_active') == 'on'
        meeting.save()
        messages.success(request, 'Meeting updated successfully!')
        return redirect('admin_meetings')
    
    return render(request, 'main/edit_meeting.html', {'meeting': meeting})

@login_required
def delete_meeting(request, meeting_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    meeting = Meeting.objects.get(id=meeting_id)
    meeting.delete()
    messages.success(request, 'Meeting deleted successfully!')
    return redirect('admin_meetings')

@login_required
def edit_announcement(request, announcement_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    announcement = Announcement.objects.get(id=announcement_id)
    if request.method == 'POST':
        announcement.title = request.POST.get('title')
        announcement.content = request.POST.get('content')
        announcement.announcement_type = request.POST.get('announcement_type')
        announcement.is_active = request.POST.get('is_active') == 'on'
        announcement.save()
        messages.success(request, 'Announcement updated successfully!')
        return redirect('admin_announcements')
    
    return render(request, 'main/edit_announcement.html', {'announcement': announcement})

@login_required
def delete_announcement(request, announcement_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    announcement = Announcement.objects.get(id=announcement_id)
    announcement.delete()
    messages.success(request, 'Announcement deleted successfully!')
    return redirect('admin_announcements')

@login_required
def my_applications(request):
    applications = MembershipApplication.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'main/my_applications.html', {'applications': applications})

@login_required
def my_claims(request):
    claims = Claim.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'main/my_claims.html', {'claims': claims})

@login_required
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
def clear_notifications(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('user_dashboard')

@login_required
def delete_notification(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.delete()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
def print_financial_report(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    payments = Payment.objects.all().order_by('-created_at')
    total_revenue = payments.filter(status='approved').aggregate(total=models.Sum('amount'))['total'] or 0
    context = {'payments': payments, 'total_revenue': total_revenue}
    return render(request, 'main/reports/financial_report.html', context)

@login_required
def print_shares_report(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    shares = Share.objects.all().order_by('-created_at')
    total_shares = shares.filter(status='approved').aggregate(total=models.Sum('shares_purchased'))['total'] or 0
    total_value = total_shares * 20  # $20 per share
    context = {'shares': shares, 'total_shares': total_shares, 'total_value': total_value}
    return render(request, 'main/reports/shares_report.html', context)

@login_required
def print_members_report(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    profiles = UserProfile.objects.select_related('user').all()
    applications = MembershipApplication.objects.all()
    context = {'profiles': profiles, 'applications': applications}
    return render(request, 'main/reports/members_report.html', context)

@login_required
def print_claims_report(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    claims = Claim.objects.all().order_by('-created_at')
    total_claims = claims.filter(status='approved').aggregate(total=models.Sum('amount_requested'))['total'] or 0
    context = {'claims': claims, 'total_claims': total_claims}
    return render(request, 'main/reports/claims_report.html', context)

@login_required
def review_application(request, app_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    application = MembershipApplication.objects.get(id=app_id)
    if request.method == 'POST':
        application.status = request.POST.get('status')
        application.admin_notes = request.POST.get('admin_notes')
        application.save()
        messages.success(request, 'Application updated successfully!')
        return redirect('admin_dashboard')
    
    return render(request, 'main/review/review_application.html', {'application': application})

@login_required
def review_payment(request, payment_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    payment = Payment.objects.get(id=payment_id)
    if request.method == 'POST':
        payment.status = request.POST.get('status')
        payment.admin_notes = request.POST.get('admin_notes')
        payment.save()
        messages.success(request, 'Payment updated successfully!')
        return redirect('admin_dashboard')
    
    return render(request, 'main/review/review_payment.html', {'payment': payment})

@login_required
def review_claim(request, claim_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    claim = Claim.objects.get(id=claim_id)
    if request.method == 'POST':
        claim.status = request.POST.get('status')
        claim.admin_notes = request.POST.get('admin_notes')
        claim.save()
        messages.success(request, 'Claim updated successfully!')
        return redirect('admin_dashboard')
    
    return render(request, 'main/review/review_claim.html', {'claim': claim})

@login_required
def review_share(request, share_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    share = Share.objects.get(id=share_id)
    if request.method == 'POST':
        share.status = request.POST.get('status')
        share.admin_notes = request.POST.get('admin_notes')
        share.save()
        
        # Update user profile if approved
        if share.status == 'approved':
            profile, created = UserProfile.objects.get_or_create(user=share.user)
            total_approved_shares = Share.objects.filter(
                user=share.user, status='approved'
            ).aggregate(total=models.Sum('shares_purchased'))['total'] or 0
            profile.shares_owned = total_approved_shares
            
            if profile.shares_owned > 20 and profile.is_deactivated:
                profile.is_deactivated = False
                profile.status = 'active'
            
            profile.save()
        
        messages.success(request, 'Share purchase updated successfully!')
        return redirect('admin_dashboard')
    
    return render(request, 'main/review/review_share.html', {'share': share})

@login_required
def view_message(request, message_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    message = ContactMessage.objects.get(id=message_id)
    if request.method == 'POST':
        # Send reply
        Message.objects.create(
            sender=request.user,
            recipient=message.user,
            subject=f"Re: {message.subject}",
            content=request.POST.get('reply_content')
        )
        message.is_read = True
        message.save()
        messages.success(request, 'Reply sent successfully!')
        return redirect('admin_dashboard')
    
    return render(request, 'main/review/view_message.html', {'message': message})

@login_required
def user_inbox(request):
    received_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')
    context = {
        'received_messages': received_messages,
        'sent_messages': sent_messages
    }
    return render(request, 'main/user_inbox.html', context)

@login_required
def notifications(request):
    filter_period = request.GET.get('period', 'all')
    
    notifications = Notification.objects.filter(user=request.user)
    
    # Apply date filters
    if filter_period == 'today':
        notifications = notifications.filter(created_at__date=timezone.now().date())
    elif filter_period == 'week':
        week_ago = timezone.now() - timezone.timedelta(days=7)
        notifications = notifications.filter(created_at__gte=week_ago)
    elif filter_period == 'month':
        month_ago = timezone.now() - timezone.timedelta(days=30)
        notifications = notifications.filter(created_at__gte=month_ago)
    
    notifications = notifications.order_by('-created_at')
    
    context = {
        'notifications': notifications,
        'filter_period': filter_period
    }
    return render(request, 'main/notifications.html', context)

@login_required
def delete_all_notifications(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user).delete()
        messages.success(request, 'All notifications deleted successfully.')
    return redirect('notifications')

@login_required
def admin_create_notification(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type', 'general')
        
        # Create notification for all users
        users = User.objects.filter(is_active=True)
        for user in users:
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message
            )
        
        messages.success(request, f'Notification sent to {users.count()} users.')
        return redirect('admin_notifications')
    
    return render(request, 'main/admin/create_notification.html')

@login_required
def reply_message(request, message_id):
    try:
        original_message = Message.objects.get(id=message_id, recipient=request.user)
    except Message.DoesNotExist:
        messages.error(request, 'Message not found.')
        return redirect('user_inbox')
    
    if request.method == 'POST':
        reply_content = request.POST.get('content')
        
        # Create reply message
        Message.objects.create(
            sender=request.user,
            recipient=original_message.sender,
            subject=f"Re: {original_message.subject}",
            content=reply_content
        )
        
        # Create notification for recipient
        Notification.objects.create(
            user=original_message.sender,
            notification_type='general',
            title='New Message Reply',
            message=f'You have received a reply from {request.user.username}'
        )
        
        # Mark original as read
        original_message.is_read = True
        original_message.save()
        
        messages.success(request, 'Reply sent successfully!')
        return redirect('user_inbox')
    
    return render(request, 'main/reply_message.html', {'message': original_message})

@login_required
def user_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update user basic info
        request.user.first_name = request.POST.get('first_name')
        request.user.last_name = request.POST.get('last_name')
        request.user.email = request.POST.get('email')
        request.user.save()
        
        # Update profile info
        profile.phone = request.POST.get('phone')
        profile.address = request.POST.get('address')
        profile.city = request.POST.get('city')
        profile.state = request.POST.get('state')
        profile.zip_code = request.POST.get('zip_code')
        profile.emergency_contact_name = request.POST.get('emergency_contact_name')
        profile.emergency_contact_phone = request.POST.get('emergency_contact_phone')
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('user_profile')
    
    return render(request, 'main/user_profile.html', {'profile': profile})

@login_required
def send_message_to_admin(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        content = request.POST.get('content')
        
        # Get admin users
        admin_users = User.objects.filter(is_staff=True)
        if admin_users.exists():
            for admin in admin_users:
                Message.objects.create(
                    sender=request.user,
                    recipient=admin,
                    subject=subject,
                    content=content
                )
                
                # Create notification for admin
                Notification.objects.create(
                    user=admin,
                    notification_type='general',
                    title='New Message Received',
                    message=f'You have received a new message from {request.user.username}: {subject}'
                )
        
        messages.success(request, 'Message sent to admin successfully!')
        return redirect('user_inbox')
    
    return render(request, 'main/send_message.html')

@login_required
def admin_applications(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    applications = MembershipApplication.objects.all().order_by('-created_at')
    return render(request, 'main/admin/applications.html', {'applications': applications})

@login_required
def admin_payments(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    payments = Payment.objects.all().order_by('-created_at')
    return render(request, 'main/admin/payments.html', {'payments': payments})

@login_required
def admin_claims(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    claims = Claim.objects.all().order_by('-created_at')
    return render(request, 'main/admin/claims.html', {'claims': claims})

@login_required
def admin_shares(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    shares = Share.objects.all().order_by('-created_at')
    return render(request, 'main/admin/shares.html', {'shares': shares})

@login_required
def admin_messages(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    contact_messages = ContactMessage.objects.all().order_by('-created_at')
    user_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    return render(request, 'main/admin/messages.html', {
        'contact_messages': contact_messages,
        'user_messages': user_messages
    })

@login_required
def admin_notifications(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    notifications = Notification.objects.all().order_by('-created_at')
    return render(request, 'main/admin/notifications.html', {'notifications': notifications})

@login_required
def admin_deduction_history(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    deductions = ShareDeduction.objects.all().order_by('-created_at')
    return render(request, 'main/admin/deduction_history.html', {'deductions': deductions})

@login_required
def double_application_view(request):
    if request.method == 'POST':
        # Create double membership application
        application = MembershipApplication.objects.create(
            user=request.user,
            application_type='double',
            first_name=request.POST.get('first_name'),
            middle_name=request.POST.get('middle_name', ''),
            last_name=request.POST.get('last_name'),
            email=request.POST.get('email'),
            address=request.POST.get('address'),
            phone_main=request.POST.get('phone_main'),
            minnesota_id=request.FILES.get('minnesota_id'),
            spouse=request.POST.get('spouse', ''),
            spouse_phone=request.POST.get('spouse_phone', ''),
            authorized_rep=request.POST.get('authorized_rep', ''),
            child_1=request.POST.get('child_1', ''),
            child_2=request.POST.get('child_2', ''),
            child_3=request.POST.get('child_3', ''),
            child_4=request.POST.get('child_4', ''),
            child_5=request.POST.get('child_5', ''),
            parent_1=request.POST.get('parent_1', ''),
            parent_2=request.POST.get('parent_2', ''),
            sibling_1=request.POST.get('sibling_1', ''),
            sibling_2=request.POST.get('sibling_2', '')
        )
        
        # Send email notification
        send_mail(
            'New Double Membership Application',
            f'New application from {application.first_name} {application.last_name}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
        
        messages.success(request, 'Application submitted successfully! Please proceed to payment ($400).')
        return redirect('payments')
    return render(request, 'main/double_application.html')