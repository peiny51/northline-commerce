import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Auth0Provider } from '@auth0/auth0-react';

import App from './App';
import './style.css';

const domain = import.meta.env.VITE_AUTH0_DOMAIN;
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID;

const storefront = (
  <BrowserRouter>
    <App />
  </BrowserRouter>
);

const root = document.getElementById('root');

if (domain && clientId) {
  createRoot(root).render(
    <Auth0Provider
  domain={domain}
  clientId={clientId}
  authorizationParams={{
    redirect_uri: window.location.origin,
    audience: import.meta.env.VITE_AUTH0_AUDIENCE,
  }}
  cacheLocation="localstorage"
  useRefreshTokens={true}
>
  {storefront}
</Auth0Provider>,
  );
} else {
  createRoot(root).render(storefront);
}