import { supabase } from './supabase';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

export async function fetchApi<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
): Promise<{ data: T | null; error: string | null; status?: number }> {
  try {
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData.session?.access_token;

    // FormData bodies (file uploads) set their own multipart Content-Type
    const isForm = typeof FormData !== 'undefined' && options.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const response = await fetch(`${API_BASE_URL}${cleanEndpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      const detail = typeof errBody.detail === 'string'
        ? errBody.detail
        : Array.isArray(errBody.detail)
          ? errBody.detail.map((d: { msg: string }) => d.msg).join('; ')
          : `Request failed with status ${response.status}`;
      // Verifier and analyst routes need a TOTP-verified session
      if (response.status === 401 && detail === 'mfa_required' && typeof window !== 'undefined'
          && !window.location.pathname.startsWith('/mfa')) {
        window.location.href = `/mfa?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
      }
      return { data: null, error: detail, status: response.status };
    }

    const data = await response.json();
    return { data, error: null, status: response.status };
  } catch (err) {
    return { data: null, error: err instanceof Error ? err.message : 'Network request failed' };
  }
}
