import axios from 'axios';

const api = axios.create({ baseURL: '/api' });
let tokenGetter = async () => null;
let demoUser = 'customer';

export function setTokenGetter(getToken) {
  tokenGetter = getToken;
}

export function setDemoUser(user) {
  demoUser = user;
}

export async function socketCredentials() {
  return { token: await tokenGetter(), demo_user: demoUser };
}

api.interceptors.request.use(async config => {
  const token = await tokenGetter();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  } else if (import.meta.env.VITE_DEMO_MODE === 'true') {
    // The backend accepts this header only in explicitly enabled local demo mode.
    config.headers['X-Demo-User'] = demoUser;
  }
  return config;
});

export default api;
