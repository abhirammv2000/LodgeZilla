import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HostPage from './HostPage';

// HostPage reads the host id out of the JWT via useAuth(), so the real
// AuthProvider (jwtToken defaults to null, only set via a user login action)
// isn't useful here - mocking the hook directly is the standard way to feed
// a component a fixed auth state without wiring the whole provider tree.
jest.mock('../services/AuthContext', () => ({
  useAuth: () => ({ jwtToken: 'fake.token' }),
}));

// decodeJwt (see services/jwt.js) is jwt-decode under the hood; stub it so
// the test doesn't depend on constructing a real base64url JWT string.
jest.mock('../services/jwt', () => ({
  decodeJwt: () => ({ sub: '42' }),
}));

const PROPERTIES = [
  { property_id: 1, title: 'Cabin', location: 'Tahoe', rating: 4.8, price: 200 },
  { property_id: 2, title: 'Loft', location: 'Austin', rating: 4.2, price: 150 },
];

function renderHostPage() {
  return render(
    <MemoryRouter>
      <HostPage />
    </MemoryRouter>
  );
}

describe('HostPage property list', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders each property from a single fetch().json() parse', async () => {
    // The backend now returns a plain JSON array (see backend/app/routes
    // /listings.py's _serialize docstring for why this used to need a
    // second, manual JSON.parse on the frontend). fetch's own .json() is
    // the only parse step in this response chain; if HostPage still ran a
    // second JSON.parse over the array HostApi.getProperties already
    // returned, that call would throw ("[object Object] is not valid
    // JSON") and this test would fail via the console.error below, not
    // render the table.
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => PROPERTIES,
    });

    renderHostPage();

    await waitFor(() => {
      expect(screen.getByText('Cabin')).toBeInTheDocument();
    });
    expect(screen.getByText('Loft')).toBeInTheDocument();
    expect(screen.getByText('Tahoe')).toBeInTheDocument();
  });

  it('shows the empty state when the host has no properties', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });

    renderHostPage();

    await waitFor(() => {
      expect(screen.getByText(/such empty/i)).toBeInTheDocument();
    });
  });

  it('logs rather than crashes when the fetch itself fails', async () => {
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500 });

    renderHostPage();

    await waitFor(() => {
      expect(consoleError).toHaveBeenCalled();
    });
    // Still on the page, not a blank crash screen.
    expect(screen.getByText('Host Page')).toBeInTheDocument();
  });
});
