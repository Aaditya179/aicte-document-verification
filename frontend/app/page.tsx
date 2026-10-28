'use client';

import { useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { fetchApi } from '@/lib/api';
import { HOME, Loading, type Me } from '@/components/ui';

/** Signed in: your home page. Otherwise: the welcome page. */
export default function Home() {
  useEffect(() => {
    (async () => {
      const { data } = await supabase.auth.getSession();
      if (!data.session) return window.location.replace('/welcome');
      const me = await fetchApi<Me>('/me');
      window.location.replace(me.data ? HOME[me.data.role] : '/welcome');
    })();
  }, []);
  return <div className="mx-auto max-w-5xl px-6"><Loading what="Opening ProofPath" /></div>;
}
