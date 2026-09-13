import { jwtDecode } from 'jwt-decode';

// One shared decode, not three: Login.js used to hand-roll atob() + JSON.parse
// while HostPage.js and TouristPage.js each called jwt-decode separately, so
// a token-format change would have needed fixing in three places instead of
// one to actually take effect everywhere.

export const decodeJwt = (token) => {
  if (!token) {
    return null;
  }
  try {
    return jwtDecode(token);
  } catch (error) {
    return null;
  }
};

export const isTokenValid = (token) => {
  const decoded = decodeJwt(token);
  return !!decoded && decoded.exp > Date.now() / 1000;
};
