import { useCallback, useEffect, useState } from 'react';
import { Link, Route, Routes, useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';

import {
  AppBar,
  Badge,
  Box,
  Button,
  CircularProgress,
  Drawer,
  IconButton,
  MenuItem,
  Select,
  Toolbar,
  Typography,
} from '@mui/material';

import {
  ChatBubbleOutline,
  ShoppingBagOutlined,
} from '@mui/icons-material';

import api, { setDemoUser, setTokenGetter } from './api';

import Catalog from './pages/Catalog';
import ProductDetail from './pages/ProductDetail';
import Cart from './pages/Cart';
import Orders from './pages/Orders';
import SupportChat from './components/SupportChat';
import SupportWorkspace from './pages/SupportWorkspace';

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';

function useOptionalAuth() {
  // Auth0 is optional only when running the local demo.
  try {
    return useAuth0();
  } catch {
    return null;
  }
}

export default function App() {
  const auth = useOptionalAuth();
  const navigate = useNavigate();

  const [demoIdentity, setDemoIdentity] = useState('customer');
  const [chatOpen, setChatOpen] = useState(false);
  const [cartCount, setCartCount] = useState(0);

  const authLoading = Boolean(auth?.isLoading);
  const isAuthenticated = Boolean(auth?.isAuthenticated);

  // Register the token getter used by the shared API client.
  useEffect(() => {
    setTokenGetter(() => {
      if (DEMO_MODE) {
        return Promise.resolve(null);
      }

      if (!auth || auth.isLoading || !auth.isAuthenticated) {
        return Promise.resolve(null);
      }

      return auth.getAccessTokenSilently();
    });
  }, [
    auth?.isLoading,
    auth?.isAuthenticated,
    auth?.getAccessTokenSilently,
  ]);

  useEffect(() => {
    setDemoUser(demoIdentity);
  }, [demoIdentity]);

  const refreshCart = useCallback(async () => {
    // Do not request a protected endpoint before Auth0 is initialized.
    if (!DEMO_MODE && (authLoading || !isAuthenticated)) {
      setCartCount(0);
      return;
    }

    try {
      const { data } = await api.get('/cart');

      setCartCount(
        data.reduce(
          (total, item) => total + item.quantity,
          0,
        ),
      );
    } catch {
      setCartCount(0);
    }
  }, [authLoading, isAuthenticated]);

  // Reload the cart after login, logout, or demo identity changes.
  useEffect(() => {
    refreshCart();
  }, [refreshCart, demoIdentity]);

  const handleLogin = async () => {
    await auth.loginWithRedirect({
      appState: {
        returnTo: window.location.pathname + window.location.search,
      },
    });
  };

  const handleLogout = () => {
    setCartCount(0);

    auth.logout({
      logoutParams: {
        returnTo: window.location.origin,
      },
    });
  };

  return (
    <>
      <AppBar position="sticky" color="inherit" elevation={0}>
        <Toolbar sx={{ gap: 2, borderBottom: '1px solid #ddd' }}>
          <Typography
            component={Link}
            to="/"
            variant="h6"
            sx={{
              textDecoration: 'none',
              color: '#254c3d',
              fontWeight: 900,
              letterSpacing: 2,
            }}
          >
            NORTHLINE
          </Typography>

          <Box sx={{ flex: 1 }} />

          <Button component={Link} to="/" color="inherit">
            Shop
          </Button>

          <Button component={Link} to="/orders" color="inherit">
            Orders
          </Button>

          {DEMO_MODE && demoIdentity !== 'customer' && (
            <Button component={Link} to="/support" color="inherit">
              Staff
            </Button>
          )}

          <IconButton
            aria-label="Cart"
            onClick={() => navigate('/cart')}
          >
            <Badge badgeContent={cartCount} color="error">
              <ShoppingBagOutlined />
            </Badge>
          </IconButton>

          <IconButton
            aria-label="Customer support"
            onClick={() => setChatOpen(true)}
          >
            <ChatBubbleOutline />
          </IconButton>

          {authLoading ? (
            <CircularProgress size={20} />
          ) : isAuthenticated ? (
            <Button size="small" onClick={handleLogout}>
              Log out
            </Button>
          ) : auth?.loginWithRedirect ? (
            <Button size="small" onClick={handleLogin}>
              Log in
            </Button>
          ) : null}
        </Toolbar>
      </AppBar>

      {DEMO_MODE && (
        <Box
          sx={{
            background: '#e7ede7',
            py: 1,
            textAlign: 'center',
          }}
        >
          <Typography variant="caption">
            Local demo identity:
          </Typography>

          <Select
            size="small"
            value={demoIdentity}
            onChange={(event) => setDemoIdentity(event.target.value)}
            sx={{
              fontSize: 12,
              height: 28,
            }}
          >
            <MenuItem value="customer">Customer</MenuItem>
            <MenuItem value="agent">Support agent</MenuItem>
            <MenuItem value="manager">Store manager</MenuItem>
          </Select>

          <Typography
            variant="caption"
            sx={{ ml: 2 }}
          >
            Local demo only — do not deploy publicly
          </Typography>
        </Box>
      )}

      <Routes>
        <Route path="/" element={<Catalog />} />

        <Route
          path="/products/:id"
          element={<ProductDetail onAdded={refreshCart} />}
        />

        <Route
          path="/cart"
          element={<Cart onChanged={refreshCart} />}
        />

        <Route path="/orders" element={<Orders />} />

        <Route
          path="/support"
          element={<SupportWorkspace />}
        />
      </Routes>

      <Button
        variant="contained"
        startIcon={<ChatBubbleOutline />}
        onClick={() => setChatOpen(true)}
        sx={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          borderRadius: 8,
          zIndex: 3,
        }}
      >
        Ask us
      </Button>

      <Drawer
        anchor="right"
        open={chatOpen}
        onClose={() => setChatOpen(false)}
      >
        <Box
          sx={{
            width: { xs: '100vw', sm: 390 },
            height: '100%',
          }}
        >
          <SupportChat
            key={demoIdentity}
            onClose={() => setChatOpen(false)}
            onCartChanged={refreshCart}
          />
        </Box>
      </Drawer>
    </>
  );
}