import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert, Button, Container, Grid, MenuItem, TextField, Typography,
} from '@mui/material';
import api from '../api';
import { useLoad } from '../hooks/useLoad';
import { money, placeholder } from '../utils/format';

export default function ProductDetail({ onAdded }) {
  const { id } = useParams();
  const { data: product, error, loading } = useLoad(`/products/${id}`, {});
  const [variantId, setVariantId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    setVariantId(product.variants?.[0] ? String(product.variants[0].id) : '');
  }, [product.id]);

  if (loading) return <Container sx={{ py: 6 }}>Loading product...</Container>;
  if (error) return <Container sx={{ py: 6 }}><Alert severity="error">{error}</Alert></Container>;
  if (!product.id) return <Container sx={{ py: 6 }}>Product not found.</Container>;

  const variant = product.variants.find(item => String(item.id) === variantId);

  async function addToCart() {
    try {
      await api.post('/cart', { variant_id: Number(variantId), quantity });
      onAdded();
      setNotice('Added to cart!');
    } catch (requestError) {
      setNotice(requestError.response?.data?.error || requestError.message);
    }
  }

  return (
    <Container sx={{ py: 6 }}>
      <Grid container spacing={6}>
        <Grid item xs={12} md={6}>
          <img
            className="detail-image"
            src={product.image_url || placeholder(product.name)}
            alt={product.name}
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <Typography color="text.secondary">{product.brand} / {product.category}</Typography>
          <Typography variant="h3" fontWeight={800} sx={{ mt: 2 }}>{product.name}</Typography>
          <Typography variant="h5" sx={{ my: 3 }}>{money(product.price_cents)}</Typography>
          <Typography sx={{ mb: 4 }}>{product.description}</Typography>
          <TextField
            fullWidth
            select
            label="Size / Color"
            value={variantId}
            onChange={event => setVariantId(event.target.value)}
          >
            {product.variants.map(item => (
              <MenuItem key={item.id} value={String(item.id)}>
                {item.size} · {item.color} ({item.stock} left)
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Quantity"
            type="number"
            sx={{ mt: 2, width: 130 }}
            value={quantity}
            onChange={event => setQuantity(Math.max(1, Number(event.target.value) || 1))}
          />
          <Button
            variant="contained"
            size="large"
            fullWidth
            disabled={!variant || variant.stock < quantity}
            sx={{ mt: 3 }}
            onClick={addToCart}
          >
            Add to bag
          </Button>
          {notice && <Alert sx={{ mt: 2 }}>{notice}</Alert>}
        </Grid>
      </Grid>
    </Container>
  );
}
