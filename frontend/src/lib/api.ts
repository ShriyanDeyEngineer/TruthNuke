import axios, { AxiosError } from 'axios';

// API client configuration
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 second timeout for analysis requests
});

// Error handling helper
export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ error: string; detail?: string }>) => {
    if (error.response) {
      const { status, data } = error.response;
      throw new ApiError(
        data?.error || 'An error occurred',
        status,
        data?.detail
      );
    }
    throw new ApiError('Network error', 0, 'Unable to connect to the server');
  }
);

export default apiClient;
