import { useCallback, useEffect, useState } from 'react';
import api from '../api';
/** Fetch a resource and expose an explicit refresh for post-mutation updates. */
export function useLoad(path, initialValue = []) {
    const [data, setData] = useState(initialValue);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    const refresh = useCallback(async () => {
        setLoading(true);
        try {
            const response = await api.get(path);
            setData(response.data);
            setError('');
        }
        catch (requestError) {
            setError(requestError.response?.data?.error || requestError.message);
        }
        finally {
            setLoading(false);
        }
    }, [path]);
    useEffect(() => { refresh(); }, [refresh]);
    return { data, error, loading, refresh };
}
