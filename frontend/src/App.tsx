import { FormEvent, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Activity, Bell, Bot, Check, ChevronRight, Clock3, ExternalLink,
  LoaderCircle, Plus, RefreshCw, Search, Sparkles, Target, Trash2, Wallet,
} from 'lucide-react';
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';

type Product = {
  id: number; title: string; url: string; target_price: number | null;
  current_price: number | null; last_checked: string | null; last_error: string | null;
};
type History = { price: number; checked_at: string; source: string };

const money = (n: number | null | undefined) =>
  n == null ? '—' : new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 2,
  }).format(n);
const when = (s: string | null) => s ? new Date(s).toLocaleString() : 'Not checked';

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  const body = await response.json().catch(() => ({ detail: response.statusText }));
  if (!response.ok) throw Error(body.detail || 'Request failed');
  return body as T;
}

export default function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [hist, setHist] = useState<History[]>([]);
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [insight, setInsight] = useState('');
  const [online, setOnline] = useState(false);

  async function load() {
    try {
      const [list, health] = await Promise.all([
        api<Product[]>('/api/products'), api<{ status: string }>('/api/health'),
      ]);
      setProducts(list);
      setOnline(health.status === 'ok');
      const id = selected ?? list[0]?.id ?? null;
      if (id && list.some(p => p.id === id)) {
        setSelected(id);
        setHist(await api<History[]>(`/api/products/${id}/history`));
      } else if (list.length) {
        setSelected(list[0].id);
        setHist(await api<History[]>(`/api/products/${list[0].id}/history`));
      } else {
        setSelected(null);
        setHist([]);
      }
    } catch (e) {
      setOnline(false);
      setErr(e instanceof Error ? e.message : 'Backend connection failed');
    }
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (selected) api<History[]>(`/api/products/${selected}/history`).then(setHist).catch(() => setHist([]));
    else setHist([]);
  }, [selected]);

  const active = products.find(p => p.id === selected) || null;
  const chart = hist.map(h => ({
    ...h, label: new Date(h.checked_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
  }));

  function openProduct(productUrl: string) {
    try {
      const parsed = new URL(productUrl);
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        setErr('Invalid product URL.');
        return;
      }
      window.open(parsed.href, '_blank', 'noopener,noreferrer');
    } catch {
      setErr('Unable to open this product URL.');
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr('');
    try {
      const p = await api<Product>('/api/products', {
        method: 'POST', body: JSON.stringify({
          url, target_price: target ? Number(target) : null, title: name || null,
        }),
      });
      setUrl(''); setName(''); setTarget(''); setSelected(p.id);
      setMsg('Product added and first price recorded.'); await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Add failed');
    } finally { setBusy(false); }
  }

  async function check(id: number) {
    setBusyId(id); setErr('');
    try {
      const r = await api<{
        product: Product; new_price: number; notification: { sent: boolean; reason?: string };
      }>(`/api/products/${id}/check`, { method: 'POST' });
      setMsg(`Checked ${r.product.title}: ${money(r.new_price)}. ${
        r.notification.sent ? 'Slack alert sent.' : r.notification.reason || 'No alert needed.'
      }`);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Price check failed'); await load();
    } finally { setBusyId(null); }
  }

  async function demo() {
    setBusy(true); setErr('');
    try {
      const p = await api<Product>('/api/products', {
        method: 'POST',
        body: JSON.stringify({
          url: 'https://example.com/demo-product', target_price: 800, title: 'Demo Wireless Headphones',
        }),
      });
      setSelected(p.id);
      setMsg('Demo product added. This is sample data, not a live retailer price.'); await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Demo failed. Set DEMO_MODE=true in backend/.env and restart.');
    } finally { setBusy(false); }
  }

  async function insights() {
    if (!active) { setErr('Please add or select a product first, then run AI insights.'); return; }
    setBusy(true); setErr(''); setMsg('Generating AI insights…');
    try {
      const r = await api<{ summary: string }>(`/api/products/${active.id}/insights`, { method: 'POST' });
      setInsight(r.summary); setMsg('AI insights generated successfully.');
      document.getElementById('agent-actions')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'AI request failed'); setMsg('');
    } finally { setBusy(false); }
  }

  async function remove(id: number) {
    if (!confirm('Delete product and its price history?')) return;
    try {
      await api(`/api/products/${id}`, { method: 'DELETE' });
      if (selected === id) setSelected(null);
      setMsg('Product removed.'); await load();
    } catch (e) { setErr(e instanceof Error ? e.message : 'Delete failed'); }
  }

  async function editTarget() {
    if (!active) return;
    const raw = prompt('Target price in ₹ (blank clears target):', String(active.target_price ?? ''));
    if (raw === null) return;
    const value = raw.trim() === '' ? null : Number(raw);
    if (value !== null && (!Number.isFinite(value) || value <= 0)) {
      setErr('Enter a target price greater than zero.'); return;
    }
    try {
      await api(`/api/products/${active.id}/target`, {
        method: 'PATCH', body: JSON.stringify({ target_price: value }),
      });
      await load(); setMsg('Target price updated.');
    } catch (e) { setErr(e instanceof Error ? e.message : 'Update failed'); }
  }

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><div className="logo"><Activity /></div><div><b>PricePilot</b><small>AI TRACKER</small></div></div>
        <div className="workspace">◈ &nbsp; Personal workspace <ChevronRight size={14} /></div>
        <p className="label">WORKSPACE</p>
        <div className="nav active"><Activity size={17} /> Overview</div>
        <div className="nav" onClick={() => document.getElementById('url')?.focus()}><Plus size={17} /> Track a product</div>
        <div className="sidebottom">
          <div className="agent"><Bot /><b>Agent status</b>
            <span className={online ? 'online' : 'offline'}>● {online ? 'Backend connected' : 'Backend offline'}</span>
            <p>Checks run on the configured schedule.</p>
          </div>
          <small>PRICEPILOT · LOCAL EDITION</small>
        </div>
      </aside>

      <main>
        <header><div>Workspace <ChevronRight size={14} /> <b>Overview</b></div>
          <div className="right">
            <span className={online ? 'pill' : 'pill off'}>● {online ? 'System operational' : 'API disconnected'}</span>
            <button className="iconbtn" onClick={() => void load()} aria-label="Refresh dashboard"><RefreshCw size={16} /></button>
            <div className="avatar">K</div>
          </div>
        </header>

        <section className="content">
          <div className="hero"><div>
            <small className="eyebrow"><Sparkles size={13} /> INTELLIGENT PRICE MONITORING</small>
            <h1>Stay ahead of <em>every price.</em></h1>
            <p>Your agent watches products, tracks price history, and alerts you when it matters.</p>
          </div>
            <button className="primary" onClick={() => document.getElementById('url')?.focus()}><Plus size={16} /> Track new product</button>
          </div>

          {err && <div className="alert error">{err}<button onClick={() => setErr('')}>Dismiss</button></div>}
          {msg && <div className="alert success"><Check size={15} />{msg}<button onClick={() => setMsg('')}>Dismiss</button></div>}

          <div className="stats">
            <div className="stat"><span>Tracked products</span><strong>{products.length}</strong><small>Products in watchlist</small></div>
            <div className="stat"><span>Targets reached</span>
              <strong>{products.filter(p => p.current_price != null && p.target_price != null && p.current_price <= p.target_price).length}</strong>
              <small>At or below target price</small>
            </div>
            <div className="stat"><span>Needs attention</span><strong>{products.filter(p => p.last_error).length}</strong><small>Recent extraction errors</small></div>
          </div>

          <div className="sectionhead"><div><h2>Your watchlist</h2><p>Manage products and monitor price movements.</p></div>
            <button className="secondary" onClick={() => void load()}><RefreshCw size={14} /> Refresh</button>
          </div>

          <div className="layout">
            <div className="list">
              {products.length === 0 && <div className="empty"><Search size={27} /><h3>Your watchlist starts here</h3>
                <p>Add a product URL or load a demo product to explore the dashboard.</p>
                <button className="secondary" onClick={() => void demo()}><Sparkles size={14} /> Load demo product</button>
              </div>}

              {products.map(p => (
                <div key={p.id} className={'product ' + (selected === p.id ? 'chosen' : '')} onClick={() => setSelected(p.id)}>
                  <div className="thumb"><Wallet size={19} /></div>
                  <div className="prodinfo">
                    <b>{p.title}</b>
                    <small>{(() => { try { return new URL(p.url).hostname; } catch { return 'Product retailer'; } })()}</small>
                    <small>{p.last_error ? 'Check failed' : `Checked ${when(p.last_checked)}`}</small>
                    <button
                      type="button"
                      className="secondary"
                      disabled={!p.url}
                      title={`Open ${p.title} in a new tab`}
                      onClick={event => { event.stopPropagation(); openProduct(p.url); }}
                      style={{ marginTop: 8, padding: '7px 10px', fontSize: 12 }}
                    >
                      <ExternalLink size={14} /> Open Product
                    </button>
                  </div>
                  <div className="price"><b>{money(p.current_price)}</b><small>Target {money(p.target_price)}</small></div>
                </div>
              ))}

              <form className="form" onSubmit={add}>
                <h3><Plus size={16} /> Add a product</h3>
                <label htmlFor="url">Product URL</label>
                <input id="url" type="url" required placeholder="https://store.example/product" value={url} onChange={e => setUrl(e.target.value)} />
                <label htmlFor="name">Product name <small>(optional)</small></label>
                <input id="name" placeholder="e.g. Wireless headphones" value={name} onChange={e => setName(e.target.value)} />
                <label htmlFor="target">Target price in ₹ <small>(optional)</small></label>
                <input id="target" type="number" min="0.01" step="0.01" placeholder="800" value={target} onChange={e => setTarget(e.target.value)} />
                <button className="primary full" disabled={busy}>{busy ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />} Add and check price</button>
                <button type="button" className="textbtn" onClick={() => void demo()}>Load demo product instead</button>
              </form>
            </div>

            <div className="rightcol">
              <section className="panel">
                <div className="panelhead"><div><h3>Price history</h3><p>{active ? active.title : 'Select a product to view history'}</p></div>
                  {active && <button className="iconbtn" title="Open selected product" aria-label="Open selected product" onClick={() => openProduct(active.url)}><ExternalLink size={15} /></button>}
                </div>
                {active && hist.length ? <>
                  <div className="current"><div><small>Current price</small><strong>{money(active.current_price)}</strong></div><span>{hist.length} recorded check{hist.length === 1 ? '' : 's'}</span></div>
                  <div className="chart"><ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#9685ff" stopOpacity={0.25} /><stop offset="100%" stopColor="#9685ff" stopOpacity={0} />
                      </linearGradient></defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#293241" />
                      <XAxis dataKey="label" tick={{ fill: '#8d97a9', fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: '#8d97a9', fontSize: 10 }} axisLine={false} tickLine={false} width={58} tickFormatter={v => `₹${v}`} />
                      <Tooltip contentStyle={{ background: '#171e29', border: '1px solid #30394a', borderRadius: 8 }} formatter={v => [money(Number(v)), 'Price']} />
                      <Area type="monotone" dataKey="price" stroke="#9b8cff" strokeWidth={2.5} fill="url(#fill)" dot={{ r: 3 }} />
                    </AreaChart>
                  </ResponsiveContainer></div>
                </> : <div className="chartempty"><Activity size={25} /><p>{active ? 'No price history yet.' : 'Choose a product to explore price history.'}</p></div>}
                {active && <div className="chartfoot"><span><Clock3 size={13} /> Last check: {when(active.last_checked)}</span><span>{active.last_error || 'Price history saved locally'}</span></div>}
              </section>

              <section className="panel" id="agent-actions">
                <div className="panelhead"><div><h3>Agent actions</h3><p>Run checks and get AI assistance.</p></div><Bot /></div>
                <div className="action"><RefreshCw /><div><b>Check current price</b><small>Fetch and compare latest price</small></div>
                  <button className="secondary" disabled={!active || busyId === active.id} onClick={() => active && void check(active.id)}>{busyId === active?.id ? <LoaderCircle className="spin" size={14} /> : 'Run check'}</button>
                </div>
                <div className="action"><Sparkles /><div><b>AI price insights</b><small>Claude summarizes recorded history</small></div>
                  <button className="secondary" disabled={!active || busy} onClick={() => void insights()}>{busy ? '...' : 'Analyze'}</button>
                </div>
                <div className="action"><Target /><div><b>Target price</b><small>{active ? `Current target: ${money(active.target_price)}` : 'Choose a product'}</small></div>
                  <button className="secondary" disabled={!active} onClick={() => void editTarget()}>Edit</button>
                </div>
                <div className="action"><Trash2 /><div><b>Remove product</b><small>Delete product and history</small></div>
                  <button className="secondary" disabled={!active} onClick={() => active && void remove(active.id)}>Remove</button>
                </div>
                {insight && <div className="insight"><b><Sparkles size={14} /> Claude's analysis</b><div className="markdown-content"><ReactMarkdown>{insight}</ReactMarkdown></div></div>}
              </section>
              <div className="note"><Bell size={19} /><div><b>Slack notifications</b><p>Set SLACK_WEBHOOK_URL in backend/.env to receive price-drop and target-price alerts.</p></div></div>
            </div>
          </div>
          <footer>PricePilot · AI-assisted monitoring <span>Best-effort extraction; verify prices before purchase.</span></footer>
        </section>
      </main>
    </div>
  );
}
