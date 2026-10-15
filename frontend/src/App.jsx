import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useState,
} from 'react';

import {
  Link,
  Route,
  Routes,
  useNavigate,
} from 'react-router-dom';

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

import api, {
  setDemoUser,
  setTokenGetter,
} from './api';

import Catalog from './pages/Catalog';
import ProductDetail from './pages/ProductDetail';
import Cart from './pages/Cart';
import Orders from './pages/Orders';
import SupportChat from './components/SupportChat';
import SupportWorkspace from './pages/SupportWorkspace';

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';


function useOptionalAuth() {
  // Auth0 is optional only when using the local demo mode.
  try {
    return useAuth0();
  } catch {
    return null;
  }
}


function LoginRequired({ onLogin }) {
  return (
    <Box
      sx={{
        py: 8,
        px: 3,
        textAlign: 'center',
      }}
    >
      <Typography variant="h6" fontWeight={700}>
        Please log in to continue.
      </Typography>

      <Typography
        color="text.secondary"
        sx={{ mt: 1 }}
      >
        Sign in to access your cart, orders, and support.
      </Typography>

      <Button
        variant="contained"
        sx={{ mt: 3 }}
        onClick={onLogin}
      >
        Log in
      </Button>
    </Box>
  );
}


export default function App() {
  const auth = useOptionalAuth();
  const navigate = useNavigate();

  const [demoIdentity, setDemoIdentity] = useState('customer');
  const [chatOpen, setChatOpen] = useState(false);
  const [cartCount, setCartCount] = useState(0);

  const authLoading = Boolean(auth?.isLoading);
  const isAuthenticated = Boolean(auth?.isAuthenticated);

  const canAccessProtectedPages = DEMO_MODE || isAuthenticated;

  // Register the Auth0 token getter before child page effects run.
  // This prevents protected API calls from using the initial empty getter.
  useLayoutEffect(() => {
    setTokenGetter(async () => {
      if (DEMO_MODE) {
        return null;
      }

      if (!auth?.isAuthenticated) {
        return null;
      }

      return auth.getAccessTokenSilently();
    });

    return () => {
      // Clear the callback when the component unmounts.
      setTokenGetter(async () => null);
    };
  }, [
    auth?.isAuthenticated,
    auth?.getAccessTokenSilently,
  ]);

  // Keep the selected demo identity synchronized with the API client.
  useEffect(() => {
    setDemoUser(demoIdentity);
  }, [demoIdentity]);

  const refreshCart = useCallback(async () => {
    // Never query a protected API before authentication is ready.
    if (!canAccessProtectedPages || authLoading) {
      setCartCount(0);
      return;
    }

    try {
      const { data } = await api.get('/cart');

      const count = data.reduce(
        (total, item) => total + item.quantity,
        0,
      );

      setCartCount(count);
    } catch (error) {
      console.error('Unable to load cart:', error);
      setCartCount(0);
    }
  }, [
    canAccessProtectedPages,
    authLoading,
  ]);

  // Refresh after authentication or demo identity changes.
  useEffect(() => {
    refreshCart();
  }, [
    refreshCart,
    demoIdentity,
  ]);

  const handleLogin = async () => {
    if (!auth?.loginWithRedirect) {
      return;
    }

    await auth.loginWithRedirect();
  };

  const handleLogout = () => {
    if (!auth?.logout) {
      return;
    }

    setCartCount(0);
    setChatOpen(false);

    auth.logout({
      logoutParams: {
        returnTo: window.location.origin,
      },
    });
  };

  const renderProtectedPage = (component) => {
    if (canAccessProtectedPages) {
      return component;
    }

    return <LoginRequired onLogin={handleLogin} />;
  };

  return (
    <>
      <AppBar
        position="sticky"
        color="inherit"
        elevation={0}
      >
        <Toolbar
          sx={{
            gap: 2,
            borderBottom: '1px solid #ddd',
          }}
        >
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

          <Button
            component={Link}
            to="/"
            color="inherit"
          >
            Shop
          </Button>

          <Button
            component={Link}
            to="/orders"
            color="inherit"
          >
            Orders
          </Button>

          {DEMO_MODE && demoIdentity !== 'customer' && (
            <Button
              component={Link}
              to="/support"
              color="inherit"
            >
              Staff
            </Button>
          )}

          <IconButton
            aria-label="Cart"
            onClick={() => navigate('/cart')}
          >
            <Badge
              badgeContent={cartCount}
              color="error"
            >
              <ShoppingBagOutlined />
            </Badge>
          </IconButton>

          <IconButton
            aria-label="Customer support"
            onClick={() => setChatOpen(true)}
          >
            <ChatBubbleOutline />
          </IconButton>

          {authLoading && !DEMO_MODE ? (
            <CircularProgress size={20} />
          ) : isAuthenticated ? (
            <Button
              size="small"
              onClick={handleLogout}
            >
              Log out
            </Button>
          ) : auth?.loginWithRedirect ? (
            <Button
              size="small"
              onClick={handleLogin}
            >
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
            onChange={(event) => {
              setDemoIdentity(event.target.value);
            }}
            sx={{
              fontSize: 12,
              height: 28,
            }}
          >
            <MenuItem value="customer">
              Customer
            </MenuItem>

            <MenuItem value="agent">
              Support agent
            </MenuItem>

            <MenuItem value="manager">
              Store manager
            </MenuItem>
          </Select>

          <Typography
            variant="caption"
            sx={{ ml: 2 }}
          >
            Local demo only — do not deploy publicly
          </Typography>
        </Box>
      )}

      {/* Wait for Auth0 before mounting pages that may request tokens. */}
      {!DEMO_MODE && authLoading ? (
        <Box
          sx={{
            py: 8,
            textAlign: 'center',
          }}
        >
          <CircularProgress />

          <Typography sx={{ mt: 2 }}>
            Checking your login...
          </Typography>
        </Box>
      ) : (
        <Routes>
          <Route
            path="/"
            element={<Catalog />}
          />

          <Route
            path="/products/:id"
            element={
              <ProductDetail onAdded={refreshCart} />
            }
          />

          <Route
            path="/cart"
            element={renderProtectedPage(
              <Cart onChanged={refreshCart} />,
            )}
          />

          <Route
            path="/orders"
            element={renderProtectedPage(
              <Orders />,
            )}
          />

          <Route
            path="/support"
            element={renderProtectedPage(
              <SupportWorkspace />,
            )}
          />
        </Routes>
      )}

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
            width: {
              xs: '100vw',
              sm: 390,
            },
            height: '100%',
          }}
        >
          {authLoading && !DEMO_MODE ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <CircularProgress />
            </Box>
          ) : canAccessProtectedPages ? (
            <SupportChat
              key={demoIdentity}
              onClose={() => setChatOpen(false)}
              onCartChanged={refreshCart}
            />
          ) : (
            <LoginRequired onLogin={handleLogin} />
          )}
        </Box>
      </Drawer>
    </>
  );
}