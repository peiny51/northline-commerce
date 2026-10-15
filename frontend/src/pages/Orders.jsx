import { useState } from 'react';

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Paper,
  Stack,
  Typography,
} from '@mui/material';

import api from '../api';
import { useLoad } from '../hooks/useLoad';
import { money } from '../utils/format';

const STATUS_LABELS = {
  pending: 'Awaiting payment',
  paid: 'Paid',
  expired: 'Expired',
  cancelled: 'Cancelled',
};

const STATUS_COLORS = {
  pending: 'warning',
  paid: 'success',
  expired: 'default',
  cancelled: 'default',
};

function getErrorMessage(error) {
  const detail = error.response?.data;

  if (typeof detail?.detail === 'string') {
    return detail.detail;
  }

  if (typeof detail?.error === 'string') {
    return detail.error;
  }

  if (Array.isArray(detail)) {
    return detail.join(' ');
  }

  return error.message || 'Unable to complete the request.';
}

export default function Orders() {
  const {
    data: orders,
    error,
    loading,
    refresh,
  } = useLoad('/orders');

  const [busyOrderId, setBusyOrderId] = useState(null);
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');

  async function payNow(orderId) {
    if (busyOrderId) return;

    setBusyOrderId(orderId);
    setActionError('');
    setNotice('');

    try {
      const { data } = await api.post(`/orders/${orderId}/pay`);

      if (data.checkout_url) {
        // Continue the original Stripe Checkout session.
        window.location.assign(data.checkout_url);
        return;
      }

      setNotice(data.message || 'Payment status updated.');
      await refresh();
    } catch (error) {
      setActionError(getErrorMessage(error));
      await refresh();
    } finally {
      setBusyOrderId(null);
    }
  }

  async function cancelOrder(orderId) {
    if (busyOrderId) return;

    const confirmed = window.confirm(
      'Cancel this unpaid order? Reserved items will be returned to stock.',
    );

    if (!confirmed) return;

    setBusyOrderId(orderId);
    setActionError('');
    setNotice('');

    try {
      const { data } = await api.post(
        `/orders/${orderId}/cancel`,
      );

      setNotice(data.message || 'Order updated.');
      await refresh();
    } catch (error) {
      setActionError(getErrorMessage(error));
      await refresh();
    } finally {
      setBusyOrderId(null);
    }
  }

  return (
    <Container sx={{ py: 6 }}>
      <Typography
        variant="h4"
        fontWeight={800}
        gutterBottom
      >
        My orders
      </Typography>

      {loading && (
        <Stack
          direction="row"
          spacing={2}
          alignItems="center"
          sx={{ my: 3 }}
        >
          <CircularProgress size={24} />
          <Typography color="text.secondary">
            Loading orders...
          </Typography>
        </Stack>
      )}

      {error && !loading && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Unable to load orders: {error}
        </Alert>
      )}

      {actionError && (
        <Alert
          severity="error"
          sx={{ mb: 3 }}
          onClose={() => setActionError('')}
        >
          {actionError}
        </Alert>
      )}

      {notice && (
        <Alert
          severity="success"
          sx={{ mb: 3 }}
          onClose={() => setNotice('')}
        >
          {notice}
        </Alert>
      )}

      {!loading && !error && orders.length === 0 && (
        <Typography color="text.secondary">
          No orders yet.
        </Typography>
      )}

      {!loading && !error && orders.map((order) => {
        const isPending = order.status === 'pending';
        const isBusy = busyOrderId === order.id;
        const actionsDisabled = Boolean(busyOrderId);

        return (
          <Paper
            key={order.id}
            sx={{
              p: 3,
              mb: 2,
            }}
          >
            <Stack
              direction={{
                xs: 'column',
                sm: 'row',
              }}
              justifyContent="space-between"
              alignItems={{
                xs: 'flex-start',
                sm: 'center',
              }}
              spacing={1}
            >
              <Typography
                variant="h6"
                sx={{ overflowWrap: 'anywhere' }}
              >
                Order #{order.id}
              </Typography>

              <Chip
                label={
                  STATUS_LABELS[order.status] || order.status
                }
                color={
                  STATUS_COLORS[order.status] || 'default'
                }
              />
            </Stack>

            <Typography
              color="text.secondary"
              sx={{ mt: 1 }}
            >
              {new Date(order.created_at).toLocaleDateString()}
              {' · '}
              {money(order.total_cents)}
            </Typography>

            <Box sx={{ mt: 2 }}>
              {order.items.map((item) => (
                <Typography
                  key={item.id}
                  sx={{ mt: 1 }}
                >
                  {item.quantity} × {item.name}
                </Typography>
              ))}
            </Box>

            {isPending && (
              <Stack
                direction="row"
                spacing={2}
                sx={{ mt: 3 }}
              >
                <Button
                  variant="contained"
                  disabled={actionsDisabled}
                  onClick={() => payNow(order.id)}
                >
                  {isBusy ? 'Processing...' : 'Pay Now'}
                </Button>

                <Button
                  variant="outlined"
                  color="error"
                  disabled={actionsDisabled}
                  onClick={() => cancelOrder(order.id)}
                >
                  Cancel Order
                </Button>
              </Stack>
            )}
          </Paper>
        );
      })}
    </Container>
  );
}