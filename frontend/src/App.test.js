import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import axios from 'axios';

jest.mock('axios');

const menuResponse = [
  {
    id: 1,
    name: 'Pizza',
    description: 'Cheesy pizza',
    price: 199,
    is_available: true,
  },
];

const mockApi = () => {
  axios.get.mockImplementation((url) => {
    if (url.includes('/menu/')) {
      return Promise.resolve({ data: menuResponse });
    }
    if (url.includes('/orders/')) {
      return Promise.resolve({ data: [] });
    }
    return Promise.reject(new Error('unknown endpoint'));
  });
};

const fillOrderForm = async () => {
  await userEvent.type(screen.getByLabelText(/customer name/i), 'John Doe');
  await userEvent.type(screen.getByLabelText(/whatsapp number/i), '+919876543210');
  await userEvent.click(screen.getByRole('button', { name: /increase pizza/i }));
};

test('renders dashboard', async () => {
  mockApi();

  render(<App />);
  expect(await screen.findByText(/Fresh food, fast updates/i)).toBeInTheDocument();
  expect(screen.getByText(/Your cart is empty/i)).toBeInTheDocument();
});

test('shows a validation message when customer name contains numbers', async () => {
  mockApi();
  render(<App />);

  const customerName = await screen.findByLabelText(/customer name/i);
  await userEvent.type(customerName, 'John123');

  expect(screen.getByText(/Enter letters and spaces only/i)).toBeInTheDocument();
});

test('shows a validation message when customer name contains hyphens or apostrophes', async () => {
  mockApi();
  render(<App />);

  const customerName = await screen.findByLabelText(/customer name/i);
  await userEvent.type(customerName, 'John-Doe');

  expect(screen.getByText(/Enter letters and spaces only/i)).toBeInTheDocument();
});

test('accepts whitespace-only customer name input', async () => {
  mockApi();
  render(<App />);

  const customerName = await screen.findByLabelText(/customer name/i);
  await userEvent.type(customerName, ' ');

  expect(screen.queryByText(/customer name is required/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Enter letters and spaces only/i)).not.toBeInTheDocument();
});

test('shows an inline success message after a successful order', async () => {
  mockApi();
  axios.post.mockResolvedValueOnce({ data: {} });
  render(<App />);

  await screen.findByRole('button', { name: /increase pizza/i });
  await fillOrderForm();

  await userEvent.click(screen.getByRole('button', { name: /send order/i }));

  await waitFor(() => {
    expect(screen.getByText(/Order placed successfully/i, { selector: '.orderFeedback' })).toBeInTheDocument();
  });
});

test('shows an inline failure message when order placement fails', async () => {
  mockApi();
  axios.post.mockRejectedValueOnce({
    response: {
      data: {
        detail: 'Unable to place order right now.',
      },
    },
  });
  render(<App />);

  await screen.findByRole('button', { name: /increase pizza/i });
  await fillOrderForm();

  await userEvent.click(screen.getByRole('button', { name: /send order/i }));

  await waitFor(() => {
    expect(screen.getByText(/Unable to place order right now./i, { selector: '.orderFeedbackError' })).toBeInTheDocument();
  });
});
