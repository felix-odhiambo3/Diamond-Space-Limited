
from django.db import transaction
from django.db.models import Q, Value
from django.db.models.functions import Replace
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Customer,
    Vehicle,
    VehicleCategory,
    CreditAccount,
    CreditLedgerEntry,
    CreditPaymentAllocation,
)

from .serializers import (
    CustomerSerializer,
    VehicleSerializer,
    VehicleCategorySerializer,
    CreditAccountSerializer,
    CreditLedgerEntrySerializer,
    CreditPaymentCreateSerializer,
    CreditPaymentAllocationSerializer,
)

from .permissions import (
    CustomerAccess,
    VehicleAccess,
    VehicleCategoryAccess,
    CreditAccountAccess,
    CreditLedgerAccess,
)

from .services import record_credit_payment, CreditLedgerError


# CUSTOMER VIEWS

class CustomerListCreateView(generics.ListCreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, CustomerAccess]


class CustomerDetailView(generics.RetrieveUpdateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, CustomerAccess]


# VEHICLE CATEGORY VIEWS

class VehicleCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = VehicleCategorySerializer
    permission_classes = [IsAuthenticated, VehicleCategoryAccess]

    def get_queryset(self):
        return VehicleCategory.objects.filter(
            is_active=True
        ).order_by('name')


# VEHICLE VIEWS

class VehicleListCreateView(generics.ListCreateAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated, VehicleAccess]

    def get_queryset(self):
        queryset = Vehicle.objects.select_related(
            'customer',
            'branch',
            'category',
        ).all()

        raw_search = self.request.query_params.get(
            'search',
            ''
        ).strip()

        if raw_search:
            registration_search = ''.join(
                raw_search.split()
            ).upper()

            queryset = queryset.annotate(
                registration_compact=Replace(
                    'registration_number',
                    Value(' '),
                    Value(''),
                )
            ).filter(
                Q(
                    registration_compact__icontains=registration_search
                )
                | Q(make_model__icontains=raw_search)
            )

        return queryset.order_by('registration_number')


class VehicleDetailView(generics.RetrieveUpdateAPIView):
    queryset = Vehicle.objects.select_related(
        'customer',
        'branch',
        'category',
    ).all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated, VehicleAccess]


# CREDIT ACCOUNT VIEWS

class CreditAccountListCreateView(generics.ListCreateAPIView):
    serializer_class = CreditAccountSerializer
    permission_classes = [IsAuthenticated, CreditAccountAccess]

    def get_queryset(self):
        return CreditAccount.objects.select_related(
            'customer',
            'approved_by',
        ).all()


class CreditAccountDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CreditAccountSerializer
    permission_classes = [IsAuthenticated, CreditAccountAccess]

    def get_queryset(self):
        return CreditAccount.objects.select_related(
            'customer',
            'approved_by',
        ).all()


class CreditAccountApproveView(APIView):
    permission_classes = [IsAuthenticated, CreditAccountAccess]

    @transaction.atomic
    def post(self, request, pk):
        account = get_object_or_404(
            CreditAccount.objects.select_for_update().select_related(
                'customer'
            ),
            pk=pk
        )

        if account.status != CreditAccount.Status.PENDING:
            return Response(
                {'detail': 'Only pending accounts can be approved.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not account.customer.is_active:
            return Response(
                {
                    'detail': (
                        'Cannot approve an account belonging to '
                        'an inactive customer.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        account.status = CreditAccount.Status.ACTIVE
        account.approved_by = request.user
        account.approved_at = timezone.now()

        account.save(update_fields=[
            'status',
            'approved_by',
            'approved_at',
            'updated_at',
        ])

        return Response(
            CreditAccountSerializer(account).data,
            status=status.HTTP_200_OK
        )


class CreditAccountSuspendView(APIView):
    permission_classes = [IsAuthenticated, CreditAccountAccess]

    @transaction.atomic
    def post(self, request, pk):
        account = get_object_or_404(
            CreditAccount.objects.select_for_update(),
            pk=pk
        )

        if account.status != CreditAccount.Status.ACTIVE:
            return Response(
                {'detail': 'Only active accounts can be suspended.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        account.status = CreditAccount.Status.SUSPENDED
        account.save(update_fields=['status', 'updated_at'])

        return Response(
            CreditAccountSerializer(account).data,
            status=status.HTTP_200_OK
        )


class CreditAccountCloseView(APIView):
    permission_classes = [IsAuthenticated, CreditAccountAccess]

    @transaction.atomic
    def post(self, request, pk):
        account = get_object_or_404(
            CreditAccount.objects.select_for_update(),
            pk=pk
        )

        if account.status == CreditAccount.Status.CLOSED:
            return Response(
                {'detail': 'This account is already closed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if account.outstanding_balance > 0:
            return Response(
                {
                    'detail': (
                        'This account cannot be closed because '
                        'there is an outstanding balance.'
                    ),
                    'outstanding_balance': str(
                        account.outstanding_balance
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        account.status = CreditAccount.Status.CLOSED
        account.save(update_fields=['status', 'updated_at'])

        return Response(
            CreditAccountSerializer(account).data,
            status=status.HTTP_200_OK
        )


# CREDIT LEDGER VIEWS

class CreditAccountLedgerView(generics.ListAPIView):
    serializer_class = CreditLedgerEntrySerializer
    permission_classes = [IsAuthenticated, CreditLedgerAccess]

    def get_queryset(self):
        return CreditLedgerEntry.objects.filter(
            account_id=self.kwargs['pk']
        ).select_related(
            'account',
            'created_by',
        ).order_by('-created_at')


class CreditAccountPaymentView(APIView):
    permission_classes = [IsAuthenticated, CreditLedgerAccess]

    def post(self, request, pk):
        serializer = CreditPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = record_credit_payment(
                account_id=pk,
                amount=serializer.validated_data['amount'],
                description=serializer.validated_data['description'],
                idempotency_key=serializer.validated_data[
                    'idempotency_key'
                ],
                received_by=request.user,
                reference_type=serializer.validated_data.get(
                    'reference_type', ''
                ),
                reference_id=serializer.validated_data.get(
                    'reference_id', ''
                ),
            )

        except CreditLedgerError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            CreditLedgerEntrySerializer(payment).data,
            status=status.HTTP_201_CREATED
        )


class CreditAccountAllocationsView(generics.ListAPIView):
    serializer_class = CreditPaymentAllocationSerializer
    permission_classes = [IsAuthenticated, CreditLedgerAccess]

    def get_queryset(self):
        return CreditPaymentAllocation.objects.filter(
            payment_entry__account_id=self.kwargs['pk']
        ).select_related(
            'payment_entry',
            'charge_entry',
            'allocated_by',
        ).order_by('-created_at')
