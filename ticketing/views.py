from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.http import JsonResponse
from django.db import IntegrityError
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.db.models.functions import TruncDate, TruncDay
import json
from .models import Registration, TicketConfirmation
from .forms import RegistrationForm, TicketConfirmationForm
from django.db.models import Sum
from django.utils.timezone import now
from django.utils.timezone import localtime




def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def is_organiser(user):
    return user.is_authenticated and user.groups.filter(name='Organiser').exists()


# Public registration form for students with AJAX support
@never_cache
def register_student(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('thank_you')  # Redirect after POST - change URL name accordingly
    else:
        form = RegistrationForm()
    
    return render(request, 'ticketing/registration_form.html', {'form': form})


def thank_you(request):
    return render(request, 'ticketing/thank_you.html')


# Organiser Portal to search registrations (read-only),
# excluding registrations that are already confirmed
@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def organiser_search(request):
    query = request.GET.get('q', '')
    registrations = Registration.objects.none()
    
    if query:
        registrations = Registration.objects.filter(
            Q(srn__icontains=query) | Q(name__icontains=query)
        )
    
    confirmed_students = TicketConfirmation.objects.values_list('student_id', flat=True)
    registrations = registrations.exclude(id__in=confirmed_students)
    
    return render(request, 'ticketing/organiser_search.html', {
        'registrations': registrations,
        'query': query
    })


# Organiser confirms tickets
@never_cache
@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def confirm_ticket(request, registration_id):
    registration = get_object_or_404(Registration, id=registration_id)
    
    if request.method == 'POST':
        form = TicketConfirmationForm(request.POST)
        if form.is_valid():
            confirmation_exists = TicketConfirmation.objects.filter(
                student=registration
            ).exists()
            
            if confirmation_exists:
                messages.error(request, "This ticket has already been confirmed.")
                return redirect('organiser_dashboard')
            
            try:
                confirmation = form.save(commit=False)
                confirmation.student = registration
                confirmation.confirmed_by = request.user
                confirmation.save()
                messages.success(request, "Ticket confirmed successfully.")
                return redirect('organiser_dashboard')
            except IntegrityError:
                messages.error(request, "Duplicate confirmation detected.")
                return redirect('organiser_dashboard')
    else:
        form = TicketConfirmationForm()
    
    return render(request, 'ticketing/confirm_ticket.html', {
        'form': form,
        'student': registration
    })


# Organiser dashboard showing number of confirmed tickets by them
@never_cache
@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def organiser_dashboard(request):
    count = TicketConfirmation.objects.filter(confirmed_by=request.user).count()
    return render(request, 'ticketing/organiser_dashboard.html', {
        'confirmed_count': count
    })


# Admin dashboard with summary and charts data
@never_cache
@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('no_permission')
    
    total_tickets = TicketConfirmation.objects.count()
    tickets_per_organiser = (
        TicketConfirmation.objects
        .values('confirmed_by__username')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    return render(request, 'ticketing/admin_dashboard.html', {
        'total_tickets': total_tickets,
        'tickets_per_organiser': tickets_per_organiser,
    })


# API endpoint for chart data (admin)
# @login_required
# def ticket_confirmation_data(request):
#     if not request.user.is_superuser:
#         return JsonResponse({'error': 'Unauthorized'}, status=403)

#     data = (
#         TicketConfirmation.objects
#         .annotate(confirmed_hour=TruncHour('confirmed_at'))   # <-- changed here
#         .values('confirmed_hour')
#         .order_by('confirmed_hour')
#         .annotate(count=Count('id'))
#     )

#     chart_data = {
#         'labels': [entry['confirmed_hour'].strftime("%Y-%m-%d %H:00") for entry in data],
#         'counts': [entry['count'] for entry in data]
#     }
#     return JsonResponse(chart_data)




def safe_strftime(dt):
    if dt:
        return localtime(dt).strftime("%Y-%m-%d %H:00")
    return ''

@login_required
def ticket_confirmation_data(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    data = (
        TicketConfirmation.objects
        .annotate(confirmed_hour=TruncHour('confirmed_at'))
        .values('confirmed_hour')
        .order_by('confirmed_hour')
        .annotate(count=Count('id'))
    )

    chart_data = {
        'labels': [safe_strftime(entry['confirmed_hour']) for entry in data if entry['confirmed_hour'] is not None],
        'counts': [entry['count'] for entry in data if entry['confirmed_hour'] is not None],
    }
    return JsonResponse(chart_data)






# Simple no permission view (optional)
def no_permission(request):
    return render(request, 'ticketing/no_permission.html')


@never_cache
@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def registration_detail(request, registration_id):
    registration = get_object_or_404(Registration, id=registration_id)

    # Calculate the current ticket price dynamically
    ticket_price = get_current_ticket_price()

    if request.method == 'POST':
        form = TicketConfirmationForm(request.POST)
        if form.is_valid():
            print("DEBUG: FORM is valid, proceeding to save confirmation")
            if TicketConfirmation.objects.filter(student=registration).exists():
                messages.error(request, "This ticket has already been confirmed.")
                return redirect('organiser_dashboard')

            try:
                confirmation = form.save(commit=False)
                confirmation.student = registration
                confirmation.confirmed_by = request.user
                confirmation.price = ticket_price  # Save the dynamic price here
                confirmation.save()
                print("DEBUG: Confirmation saved successfully")
                messages.success(request, "Ticket confirmed successfully.")
                return redirect('organiser_dashboard')
            except Exception as e:
                print(f"ERROR saving confirmation: {e}")
                messages.error(request, f"Error saving ticket confirmation: {e}")
                return redirect('organiser_dashboard')
        else:
            print("DEBUG: FORM invalid, errors:", form.errors)
    else:
        form = TicketConfirmationForm()

    # Pass the price to template for display (readonly)
    return render(request, 'ticketing/registration_detail.html', {
        'registration': registration,
        'form': form,
        'ticket_price': ticket_price,  # Pass price for display
    })



def get_current_ticket_price():
    confirmed_count = TicketConfirmation.objects.count()
    return 300 if confirmed_count < 250 else 400


@login_required
def confirmed_tickets_list(request):
    if not request.user.is_superuser:
        return redirect('no_permission')
    
    query = request.GET.get('q', '')
    tickets = TicketConfirmation.objects.select_related('student', 'confirmed_by')
    
    if query:
        tickets = tickets.filter(
            Q(student__name__icontains=query) |
            Q(student__srn__icontains=query) |
            Q(student__prn__icontains=query) |
            Q(confirmed_by__username__icontains=query)
        )
    
    return render(request, 'ticketing/confirmed_tickets_list.html', {
        'tickets': tickets,
        'query': query,
    })


@login_required
def organiser_cash_daywise(request):
    if not request.user.is_superuser:
        return redirect('no_permission')

    cash_tickets = TicketConfirmation.objects.filter(payment_type='Cash')

    summary = (
        cash_tickets
        .annotate(confirmed_day=TruncDate('confirmed_at'))
        .values('confirmed_day', 'confirmed_by__username')
        .annotate(
            cash_count=Count('id'),
            total_cash=Sum('price')  # Sum actual prices from DB
        )
        .order_by('confirmed_day', 'confirmed_by__username')
    )

    return render(request, 'ticketing/organiser_cash_daywise.html', {
        'summary': summary,
    })


class CustomLoginView(LoginView):
    def get_success_url(self):
        user = self.request.user
        if user.is_superuser:
            return '/custom_admin/dashboard/'  # Custom admin dashboard URL
        else:
            return '/organiser/dashboard/'  # Organiser dashboard URL


class CustomLogoutView(LogoutView):
    next_page = '/accounts/login/'  # URL to redirect after logout (login page)


@csrf_exempt
@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def validate_ticket(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        ticket_id = data.get('ticket_id')
        
        try:
            ticket = TicketConfirmation.objects.get(ticket_id=ticket_id)
        except TicketConfirmation.DoesNotExist:
            return JsonResponse({'message': 'Invalid ticket.'})
        
        if ticket.verified:
            return JsonResponse({'message': 'Ticket already verified.'})
        
        return JsonResponse({
            'message': 'Valid',
            'name': ticket.student.name,
            'srn': ticket.student.srn,
            'show_verify': True
        })


@csrf_exempt
@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def verify_ticket(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        ticket_id = data.get('ticket_id')
        
        try:
            ticket = TicketConfirmation.objects.get(ticket_id=ticket_id)
        except TicketConfirmation.DoesNotExist:
            return JsonResponse({'message': 'Invalid ticket.'})
        
        if ticket.verified:
            return JsonResponse({'message': 'Ticket already verified.'})
        
        ticket.verified = True
        ticket.save()
        
        return JsonResponse({'message': 'Ticket verified successfully.'})


@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def ticket_scanner(request):
    return render(request, 'ticketing/scan_ticket.html')
