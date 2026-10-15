import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Container, Divider, Paper, TextField, Typography,
} from '@mui/material';

import api from '../api';
import { useLoad } from '../hooks/useLoad';
import { money } from '../utils/format';

export default function Cart({ onChanged }) {
  const { data: items, error, refresh } = useLoad('/cart');
  const [address, setAddress] = useState('');
  const [notice, setNotice] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const totalCents = items.reduce(
    (sum, item) => sum + item.product.price_cents * item.quantity,
    0,
  );

  async function removeItem(itemId) {
    try {
      await api.delete(`/cart/${itemId}`);
      await refresh();
      onChanged();
    } catch (requestError) {
      setNotice(requestError.response?.data?.error || requestError.message);
    }
  }

  async function updateQuantity(itemId, quantity) {
    try {
      await api.patch(`/cart/${itemId}`, { quantity });
      await refresh();
      onChanged();
    } catch (requestError) {
      setNotice(requestError.response?.data?.detail || 'Unable to update quantity.');
    }
  }

  async function checkout() {
    if (submitting) return;
    setSubmitting(true);
    setNotice('');

    try {
      // An idempotency key belongs to this attempt, not each network retry.
      const key = crypto.randomUUID();
      const { data } = await api.post(
        '/checkout',
        { shipping_address: address },
        { headers: { 'Idempotency-Key': key } },
      );

      if (data.checkout_url) {
        window.location.assign(data.checkout_url);
        return;
      }
      navigate('/orders');
    } catch (requestError) {
      const detail = requestError.response?.data;
      setNotice(detail?.error || detail?.detail || requestError.message);
    } finally {
      setSubmitting(false);
      onChanged();
    }
  }

  return (
    <Container sx={{ py: 6, maxWidth: 850 }}>
      <Typography variant="h4" fontWeight={800} gutterBottom>
        Your bag
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}

      {items.map(item => (
        <Paper
          key={item.id}
          sx={{ p: 2, mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        >
          <Box>
            <Typography fontWeight={700}>{item.product.name}</Typography>
            <Typography color="text.secondary">
              {item.variant.color} / {item.variant.size} · Qty {item.quantity} ·{' '}
              {money(item.product.price_cents)}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button
              size="small"
              disabled={item.quantity <= 1}
              onClick={() => updateQuantity(item.id, item.quantity - 1)}
            >
              −
            </Button>
            <Typography>{item.quantity}</Typography>
            <Button
              size="small"
              disabled={item.quantity >= item.variant.stock}
              onClick={() => updateQuantity(item.id, item.quantity + 1)}
            >
              +
            </Button>
            <Button color="error" onClick={() => removeItem(item.id)}>Remove</Button>
          </Box>
        </Paper>
      ))}

      {!items.length ? (
        <Typography>Your bag is empty.</Typography>
      ) : (
        <>
          <Divider sx={{ my: 3 }} />
          <Typography variant="h6">Subtotal: {money(totalCents)}</Typography>
          <Typography variant="caption" color="text.secondary">
            Prices are shown in CAD. Taxes and shipping are not included in this MVP.
          </Typography>
          <TextField
            fullWidth
            multiline
            label="Shipping address"
            sx={{ mt: 3 }}
            value={address}
            onChange={event => setAddress(event.target.value)}
          />
          <Button
            variant="contained"
            sx={{ mt: 2 }}
            onClick={checkout}
            disabled={submitting || address.trim().length < 10}
          >
            {submitting ? 'Processing...' : 'Pay with Stripe (test mode)'}
          </Button>
        </>
      )}
      {notice && <Alert severity="warning" sx={{ mt: 2 }}>{notice}</Alert>}
    </Container>
  );
}
