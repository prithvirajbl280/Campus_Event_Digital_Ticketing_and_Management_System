from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q, Sum
from django.http import JsonResponse, HttpResponse
from django.db.models.functions import TruncDate, TruncDay
from django.contrib.auth.views import LoginView, LogoutView
from django.views.decorators.cache import never_cache
from django.db import IntegrityError
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.timezone import now
import json
import csv

from .models import Registration, TicketConfirmation
from .forms import RegistrationForm, TicketConfirmationForm


def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def is_organiser(user):
    return user.is_authenticated and user.groups.filter(name='Organiser').exists()


@never_cache
def register_student(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('thank_you')
    else:
        form = RegistrationForm()
    return render(request, 'ticketing/registration_form.html', {'form': form})


def thank_you(request):
    return render(request, 'ticketing/thank_you.html')


@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def organiser_search(request):
    query = request.GET.get('q', '')
    registrations = Registration.objects.none()
    if query:
        registrations = Registration.objects.filter(Q(srn__icontains=query) | Q(name__icontains=query))
        confirmed_students = TicketConfirmation.objects.values_list('student_id', flat=True)
        registrations = registrations.exclude(id__in=confirmed_students)
    return render(request, 'ticketing/organiser_search.html', {'registrations': registrations, 'query': query})


# Dynamic ticket price helper
def get_current_ticket_price():
    confirmed_count = TicketConfirmation.objects.count()
    return 300 if confirmed_count < 250 else 400


@never_cache
@login_required
@user_passes_test(is_organiser, login_url='no_permission')
def registration_detail(request, registration_id):
    registration = get_object_or_404(Registration, id=registration_id)
    ticket_price = get_current_ticket_price()

    if request.method == 'POST':
        form = TicketConfirmationForm(request.POST)
        if form.is_valid():
            if TicketConfirmation.objects.filter(student=registration).exists():
                messages.error(request, "This ticket has already been confirmed.")
                return redirect('organiser_dashboard')

            try:
                confirmation = form.save(commit=False)
                confirmation.student = registration
                confirmation.confirmed_by = request.user
                confirmation.price = ticket_price  # set dynamic price 
                confirmation.save()
                messages.success(request, "Ticket confirmed successfully.")
                return redirect('organiser_dashboard')
            except IntegrityError:
                messages.error(request, "Duplicate confirmation detected.")
                return redirect('organiser_dashboard')
    else:
        form = TicketConfirmationForm()

    return render(request, 'ticketing/registration_detail.html', {
        'registration': registration,
        'form': form,
        'ticket_price': ticket_price,
    })


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
        .annotate(day=TruncDate('confirmed_at'))
        .values('day', 'confirmed_by__username')
        .annotate(
            cash_count=Count('id'),
            total_cash=Sum('price')  # sum actual prices
        )
        .order_by('day', 'confirmed_by__username')
    )

    return render(request, 'ticketing/organiser_cash_daywise.html', {
        'summary': summary,
    })


class CustomLoginView(LoginView):
    def get_success_url(self):
        user = self.request.user
        if user.is_superuser:
            return '/custom_admin/dashboard/'
        else:
            return '/organiser/dashboard/'


class CustomLogoutView(LogoutView):
    next_page = '/accounts/login/'


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


@staff_member_required
def pushback_admin(request):
    tickets = TicketConfirmation.objects.select_related('student', 'confirmed_by').all()

    if request.method == 'POST':
        if 'pushback_ticket_id' in request.POST:
            ticket_id = request.POST.get('pushback_ticket_id')
            TicketConfirmation.objects.filter(id=ticket_id).update(pushback=1)
            return redirect('pushback_admin')

        elif 'download' in request.POST:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=tickets.csv'
            writer = csv.writer(response)
            writer.writerow(['Ticket ID', 'Student', 'Confirmed By', 'Pushback', 'Confirmed At'])
            for ticket in tickets:
                writer.writerow([
                    ticket.ticket_id,
                    ticket.student.name,
                    ticket.confirmed_by.username if ticket.confirmed_by else 'Unknown',
                    ticket.pushback,
                    ticket.confirmed_at.strftime('%Y-%m-%d %H:%M')
                ])
            return response

    return render(request, 'ticketing/pushback_admin.html', {'tickets': tickets})
