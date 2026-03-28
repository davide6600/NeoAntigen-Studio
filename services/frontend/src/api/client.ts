/**
 * Core API Client for NeoAntigen Studio Frontend
 * Uses standard fetch with proper typing.
 */

const API_BASE_URL = '/api';

export interface ApiError {
  detail: string;
}

export class ApiClientError extends Error {
  public status: number;
  public detail: any;

  constructor(status: number, detail: any, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  // Cloning for safety in case other parts of the system are intercepting
  const responseClone = response.clone();
  const text = await responseClone.text();
  
  if (!response.ok) {
    let errorDetail = 'Unknown Error';
    try {
      const errorData = JSON.parse(text);
      errorDetail = errorData.detail || errorData.message || JSON.stringify(errorData);
    } catch {
      errorDetail = text || 'Empty response body';
    }
    throw new ApiClientError(response.status, errorDetail, `API Error ${response.status}: ${errorDetail}`);
  }
  
  if (!text || text.trim() === '') {
    return {} as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch (e) {
    console.error("JSON Parse Error. Body:", text);
    throw new ApiClientError(response.status, text, `Failed to parse JSON. See console for body.`);
  }
}

export const apiClient = {
  async get<T>(endpoint: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(`${API_BASE_URL}${endpoint}`, window.location.origin);
    if (params) {
      Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
    }
    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });
    return handleResponse<T>(response);
  },

  async post<T>(endpoint: string, data: any): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(data),
    });
    return handleResponse<T>(response);
  },

  async delete<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'DELETE',
      headers: {
        'Accept': 'application/json',
      },
    });
    return handleResponse<T>(response);
  }
};
