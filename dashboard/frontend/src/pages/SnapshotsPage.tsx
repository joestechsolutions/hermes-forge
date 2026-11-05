import { useEffect, useState } from 'react';

interface Snapshot {
  name: string;
  timestamp?: string;
  created_at?: string;
  size?: number;
  status?: string;
}

function formatBytes(bytes?: number) {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatTimestamp(ts?: string) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleString();
  } catch {
    return ts;
  }
}

export default function SnapshotsPage() {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(false);

  const fetchSnapshots = async () => {
    try {
      const resp = await fetch('/api/v1/snapshots', { cache: 'no-store' });
      if (!resp.ok) throw new Error('unavailable');
      const data = await resp.json();
      setSnapshots(Array.isArray(data) ? data : data.snapshots || []);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSnapshots();
    const timer = setInterval(fetchSnapshots, 30_000);
    return () => clearInterval(timer);
  }, []);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const name = `snapshot-${new Date().toISOString().slice(0, 16).replace('T', '-')}`;
      const response = await fetch('/api/v1/snapshots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (!response.ok) throw new Error('create failed');
      await fetchSnapshots();
    } catch {
      setError(true);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg text-[#d9ece9] tracking-wider uppercase">Snapshots</h1>
            <p className="text-[#5d7573] text-[11px] mt-0.5">
              Bootloader &amp; system state snapshots
            </p>
          </div>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="px-4 py-1.5 text-[11px] bg-[#02a0a0] text-[#071317] rounded hover:opacity-80 transition-opacity disabled:opacity-30 uppercase tracking-wider"
          >
            {creating ? 'Creating...' : '+ New Snapshot'}
          </button>
        </div>
      </div>

      {error && <p role="alert" className="text-[#ffbd65] text-xs mb-4">Snapshot data could not refresh or the snapshot was not created. No success was recorded.</p>}
      {loading ? (
        <div className="text-[#8fa8a5] text-sm">Loading snapshots...</div>
      ) : snapshots.length === 0 ? (
        <div className="bg-[#10262b] border border-[#1e383b] rounded-2xl p-6 text-center">
          <div className="text-[#5d7573] text-sm mb-2">No snapshots available</div>
          <p className="text-[#5d7573] text-[11px]">
            Create a snapshot to preserve the current system state
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {snapshots.map((snap) => (
            <div
              key={snap.name}
              className="bg-[#10262b] border border-[#1e383b] rounded-2xl px-4 py-3 flex items-center justify-between hover:border-[#02a0a0]/30 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="text-[#d9ece9] text-sm font-bold">{snap.name}</div>
                <div className="flex items-center gap-4 mt-1">
                  <span className="text-[#5d7573] text-[11px]">
                    {formatTimestamp(snap.timestamp || snap.created_at)}
                  </span>
                  <span className="text-[#5d7573] text-[11px]">
                    Size: {formatBytes(snap.size)}
                  </span>
                  {snap.status && (
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded ${
                        snap.status === 'completed' || snap.status === 'ready'
                          ? 'text-[#02a0a0] bg-[#02a0a0]/10'
                          : 'text-[#8fa8a5] bg-[#8fa8a5]/10'
                      }`}
                    >
                      {snap.status}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}