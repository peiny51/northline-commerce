import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardMedia,
  CircularProgress,
  Container,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { SearchOutlined } from '@mui/icons-material';

import api from '../api';
import { useLoad } from '../hooks/useLoad';
import { money, placeholder } from '../utils/format';

const PAGE_SIZE = 12;

export default function Catalog() {
  const [searchText, setSearchText] = useState('');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [brand, setBrand] = useState('');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [sort, setSort] = useState('newest');
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);

  const { data: categories } = useLoad('/categories');
  const { data: brands } = useLoad('/brands');
  const requestId = useRef(0);

  // Debounce text input to avoid sending a request for every keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchText.trim()), 350);
    return () => clearTimeout(timer);
  }, [searchText]);

  // Changing any filter restarts pagination from the first page.
  useEffect(() => {
    setPage(1);
    setProducts([]);
  }, [search, category, brand, minPrice, maxPrice, sort]);

  useEffect(() => {
    // Never show stale results when a previous request finishes after filters change.
    const controller = new AbortController();
    const currentRequest = ++requestId.current;

    async function fetchProducts() {
      if (minPrice !== '' && maxPrice !== '' && Number(minPrice) > Number(maxPrice)) {
        setError('Minimum price cannot exceed maximum price.');
        setProducts([]);
        setHasMore(false);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError('');

      try {
        const { data } = await api.get('/products', {
          params: {
            page,
            limit: PAGE_SIZE,
            search: search || undefined,
            category: category || undefined,
            brand: brand || undefined,
            min_price_cad: minPrice || undefined,
            max_price_cad: maxPrice || undefined,
            sort,
          },
          signal: controller.signal,
        });

        if (currentRequest !== requestId.current) return;
        setProducts(previous => page === 1 ? data.items : [...previous, ...data.items]);
        setTotal(data.total);
        setHasMore(data.has_more);
      } catch (err) {
        if (controller.signal.aborted || currentRequest !== requestId.current) return;
        setError(err.response?.data?.message || err.response?.data?.error || 'Unable to load products.');
      } finally {
        if (currentRequest === requestId.current) setLoading(false);
      }
    }

    fetchProducts();
    return () => controller.abort();
  }, [page, search, category, brand, minPrice, maxPrice, sort]);

  function clearFilters() {
    setSearchText('');
    setSearch('');
    setCategory('');
    setBrand('');
    setMinPrice('');
    setMaxPrice('');
    setSort('newest');
  }

  return (
    <>
      <Box className="hero">
        <Container>
          <Typography variant="overline" sx={{ letterSpacing: 4 }}>
            EXPLORE MORE. SPEND LESS.
          </Typography>
          <Typography variant="h2" sx={{ fontWeight: 800, maxWidth: 550 }}>
            Gear for your next adventure.
          </Typography>
          <Typography sx={{ mt: 2, maxWidth: 470 }}>
            Outdoor essentials for every season. Explore jackets, footwear and packs.
          </Typography>
          <Button variant="contained" href="#shop" sx={{ mt: 3 }}>
            Shop collection
          </Button>
        </Container>
      </Box>

      <Container id="shop" sx={{ py: 6 }}>
        <Typography variant="h4" fontWeight={800} gutterBottom>
          Shop the collection
        </Typography>

        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ my: 3 }}>
          <TextField
            label="Search"
            placeholder="Search products or brands"
            value={searchText}
            onChange={event => setSearchText(event.target.value)}
            InputProps={{ startAdornment: <SearchOutlined sx={{ mr: 1 }} /> }}
            sx={{ flex: 2 }}
          />
          <TextField
            select
            label="Category"
            value={category}
            onChange={event => setCategory(event.target.value)}
            sx={{ minWidth: 155, flex: 1 }}
          >
            <MenuItem value="">All categories</MenuItem>
            {categories.map(item => (
              <MenuItem key={item.id} value={item.name}>{item.name}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Brand"
            value={brand}
            onChange={event => setBrand(event.target.value)}
            sx={{ minWidth: 140, flex: 1 }}
          >
            <MenuItem value="">All brands</MenuItem>
            {brands.map(item => (
              <MenuItem key={item} value={item}>{item}</MenuItem>
            ))}
          </TextField>
        </Stack>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 3 }}>
          <TextField
            label="Min price (CAD)"
            type="number"
            value={minPrice}
            onChange={event => setMinPrice(event.target.value)}
            inputProps={{ min: 0, step: '0.01' }}
          />
          <TextField
            label="Max price (CAD)"
            type="number"
            value={maxPrice}
            onChange={event => setMaxPrice(event.target.value)}
            inputProps={{ min: 0, step: '0.01' }}
          />
          <TextField
            select
            label="Sort by"
            value={sort}
            onChange={event => setSort(event.target.value)}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="newest">Newest</MenuItem>
            <MenuItem value="price_asc">Price: low to high</MenuItem>
            <MenuItem value="price_desc">Price: high to low</MenuItem>
            <MenuItem value="name_asc">Name: A to Z</MenuItem>
          </TextField>
          <Button onClick={clearFilters}>Clear filters</Button>
        </Stack>

        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}
        {!error && (
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            {total} {total === 1 ? 'product' : 'products'} found
          </Typography>
        )}

        <Grid container spacing={3}>
          {products.map(product => (
            <Grid item xs={12} sm={6} md={4} key={product.id}>
              <Card
                component={Link}
                to={`/products/${product.id}`}
                sx={{ height: '100%', textDecoration: 'none', color: 'inherit' }}
              >
                <CardMedia
                  component="img"
                  image={product.image_url || placeholder(product.name)}
                  height="260"
                />
                <CardContent>
                  <Typography variant="caption" color="text.secondary">
                    {product.brand} · {product.category}
                  </Typography>
                  <Typography variant="h6">{product.name}</Typography>
                  <Typography fontWeight={800}>{money(product.price_cents)}</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {loading && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress size={30} />
          </Box>
        )}
        {!loading && !error && products.length === 0 && (
          <Typography sx={{ py: 6 }}>No products found.</Typography>
        )}
        {hasMore && !loading && (
          <Box sx={{ textAlign: 'center', mt: 5 }}>
            <Button variant="outlined" onClick={() => setPage(value => value + 1)}>
              Load more
            </Button>
          </Box>
        )}
      </Container>
    </>
  );
}
