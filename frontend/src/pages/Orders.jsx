import { Chip, Container, Paper, Stack, Typography } from '@mui/material';
import { useLoad } from '../hooks/useLoad';
import { money } from '../utils/format';

export default function Orders() {
  const { data: orders, error, loading } = useLoad('/orders');

  return (
    <Container sx={{ py: 6 }}>
      <Typography variant="h4" fontWeight={800} gutterBottom>My orders</Typography>
      {error && <Typography color="error">{error}</Typography>}
      {!loading && !orders.length && <Typography>No orders yet.</Typography>}
      {orders.map(order => (
        <Paper key={order.id} sx={{ p: 3, mb: 2 }}>
          <Stack direction="row" justifyContent="space-between">
            <Typography variant="h6">Order #{order.id}</Typography>
            <Chip label={order.status} />
          </Stack>
          <Typography color="text.secondary">
            {new Date(order.created_at).toLocaleDateString()} · {money(order.total_cents)}
          </Typography>
          {order.items.map((item, index) => (
            <Typography key={index} sx={{ mt: 1 }}>
              {item.quantity} × {item.name}
            </Typography>
          ))}
        </Paper>
      ))}
    </Container>
  );
}
