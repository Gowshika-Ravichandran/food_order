import { render, screen } from '@testing-library/react';
import App from './App';
import axios from 'axios';

jest.mock('axios');

test('renders dashboard', async () => {
  axios.get.mockImplementation((url) => {
    if (url.includes('/menu/')) {
      return Promise.resolve({ data: [] });
    }
    if (url.includes('/orders/')) {
      return Promise.resolve({ data: [] });
    }
    return Promise.reject(new Error('unknown endpoint'));
  });

  render(<App />);
  expect(await screen.findByText(/Fresh food, fast updates/i)).toBeInTheDocument();
  expect(screen.getByText(/Your cart is empty/i)).toBeInTheDocument();
});
