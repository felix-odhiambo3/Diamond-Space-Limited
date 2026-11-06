
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .services import record_credit_payment, CreditLedgerError
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Customer,
    Vehicle,
    CreditAccount,
    CreditLedgerEntry,
    CreditPaymentAllocation,
)
from .serializers import (
    CustomerSerializer,
    VehicleSerializer,
    CreditAccountSerializer,
    CreditLedgerEntrySerializer,
    CreditPaymentCreateSerializer,
    CreditPaymentAllocationSerializer,
)
from .permissions import (
    CustomerAccess,
    VehicleAccess,
    CreditAccountAccess,
    CreditLedgerAccess,
)


# CUSTOMER VIEWS

class CustomerListCreateView(generics.ListCreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, CustomerAccess]


class CustomerDetailView(generics.RetrieveUpdateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, CustomerAccess]


# VEHICLE VIEWS

class VehicleListCreateView(generics.ListCreateAPIView):
    queryset = Vehicle.objects.select_related(
        'customer', 'branch'
    ).all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated, VehicleAccess]


class VehicleDetailView(generics.RetrieveUpdateAPIView):
    queryset = Vehicle.objects.select_related(
        'customer', 'branch'
    ).all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated, VehicleAccess]


# CREDIT ACCOUNT VIEWS

class CreditAccountListCreateView(generics.ListCreateAPIView):
    serializer_class = CreditAccountSerializer
    permission_classes = [IsAuthenticated, CreditAccountAccess]

    def get_queryset(self):
        return CreditAccount.objects.select_related(
            'customer', 'approved_by'
        ).all()


class CreditAccountDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CreditAccountSerializer
    permission_classes = [IsAuthenticated, CreditAccountAccess]

    def get_queryset(self):
        return CreditAccount.objects.select_related(
            'customer', 'approved_by'
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
                {'detail': 'Cannot approve an account belonging to an inactive customer.'},
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
                idempotency_key=serializer.validated_data['idempotency_key'],
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