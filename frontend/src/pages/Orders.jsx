import {
  Alert,
  Chip,
  CircularProgress,
  Container,
  Paper,
  Stack,
  Typography,
} from '@mui/material';

import { useLoad } from '../hooks/useLoad';
import { money } from '../utils/format';


export default function Orders() {
  const {
    data: orders,
    error,
    loading,
  } = useLoad('/orders');

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

      {/* An API failure must not be displayed as an empty order history. */}
      {!loading && !error && orders.length === 0 && (
        <Typography color="text.secondary">
          No orders yet.
        </Typography>
      )}

      {!loading && !error && orders.map((order) => (
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
              label={order.status}
              color={
                order.status === 'paid'
                  ? 'success'
                  : 'default'
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

          {order.items.map((item) => (
            <Typography
              key={item.id}
              sx={{ mt: 1 }}
            >
              {item.quantity} × {item.name}
            </Typography>
          ))}
        </Paper>
      ))}
    </Container>
  );
}