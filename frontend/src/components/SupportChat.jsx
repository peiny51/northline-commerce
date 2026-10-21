import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Alert, Box, Button, Card, CardContent, CardMedia, IconButton,
  Paper, Stack, TextField, Typography,
} from '@mui/material';
import { Close, Send } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import api from '../api';
import { money, placeholder } from '../utils/format';

function RecommendationCards({ products, onClose }) {
  if (!products?.length) return null;

  return (
    <Box sx={{ display: 'flex', gap: 1, overflowX: 'auto', py: 1 }}>
      {products.map(product => (
        <Card key={product.id} sx={{ minWidth: 160 }}>
          <CardMedia
            component="img"
            image={product.image_url || placeholder(product.name)}
            height="100"
          />
          <CardContent sx={{ p: 1 }}>
            <Typography variant="body2" fontWeight={700}>{product.name}</Typography>
            <Typography variant="body2">{money(product.price_cents)}</Typography>
            <Button
              size="small"
              component={Link}
              to={`/products/${product.id}`}
              onClick={onClose}
            >
              View product
            </Button>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}

function AssistantMessage({ content }) {
  return (
    <Box sx={{
      overflowWrap: 'anywhere',
      '& p': { mt: 0, mb: 1 },
      '& p:last-child': { mb: 0 },
      '& ul, & ol': { my: 1, pl: 2.5 },
      '& li': { mb: 0.75 },
      '& li > p': { mb: 0.5 },
      '& a': { color: 'primary.main' },
    }}>
      {/* Render AI Markdown as formatted text rather than displaying ** and list markers. */}
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
        {content}
      </ReactMarkdown>
    </Box>
  );
}

function MessageBubble({ message, onClose }) {
  const isCustomer = message.sender === 'customer';
  const title = message.sender === 'ai'
    ? 'AI assistant'
    : message.sender === 'agent' ? 'Support agent' : 'You';

  return (
    <Box sx={{ display: 'flex', justifyContent: isCustomer ? 'flex-end' : 'flex-start', mb: 2 }}>
      <Box sx={{ maxWidth: '92%' }}>
        <Paper sx={{ p: 1.5, background: isCustomer ? '#e2eee4' : '#fff' }}>
          <Typography variant="caption" color="text.secondary">{title}</Typography>
          {message.sender === 'ai' ? (
            <AssistantMessage content={message.content} />
          ) : (
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{message.content}</Typography>
          )}
        </Paper>
        <RecommendationCards products={message.data?.products} onClose={onClose} />
      </Box>
    </Box>
  );
}

export default function SupportChat({ onClose, onCartChanged }) {
  const [conversation, setConversation] = useState(null);
  const [text, setText] = useState('');
  const [queueAhead, setQueueAhead] = useState(null);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api.get('/support/conversations')
      .then(({ data }) => {
        const active = data.find(item => item.status !== 'closed');
        if (active) setConversation(active);
      })
      .catch(() => setError('Sign in to access customer support.'));
  }, []);

  const refresh = useCallback(async () => {
    if (!conversation?.id) return;

    try {
      const { data } = await api.get(`/support/conversations/${conversation.id}`);
      setConversation(data);
      if (data.status === 'closed') {
        setQueueAhead(null);
        setText('');
      } else if (data.status === 'waiting') {
        const response = await api.get(`/support/conversations/${data.id}/position`);
        setQueueAhead(response.data.ahead);
      } else {
        setQueueAhead(null);
      }
      setError('');
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to refresh chat.');
    }
  }, [conversation?.id]);

  useEffect(() => {
    if (!conversation?.id) return undefined;
    let socket;
    let active = true;

    api.post(`/support/conversations/${conversation.id}/ticket`)
      .then(({ data }) => {
        if (!active) return;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        socket = new WebSocket(
          `${protocol}//${host}/ws/support/${conversation.id}/?ticket=${encodeURIComponent(data.ticket)}`,
        );
        socket.onmessage = () => refresh();
      })
      .catch(() => {});

    // Polling remains the fallback if the WebSocket disconnects.
    const timer = setInterval(refresh, 3500);
    return () => {
      active = false;
      clearInterval(timer);
      socket?.close();
    };
  }, [conversation?.id, refresh]);

  async function startConversation() {
    try {
      const { data } = await api.post('/support/conversations');
      setConversation(data);
      setError('');
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to start chat.');
    }
  }

  async function sendMessage() {
    if (!conversation || !text.trim() || sending) return;
    setSending(true);

    try {
      const { data } = await api.post(
        `/support/conversations/${conversation.id}/messages`,
        { content: text.trim() },
      );
      setConversation(data);
      setText('');
      onCartChanged?.();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Message could not be sent.');
    } finally {
      setSending(false);
    }
  }

  async function changeStatus(action) {
    try {
      const { data } = await api.post(`/support/conversations/${conversation.id}/${action}`);
      setConversation(data);
      if (data.status === 'closed') {
        setText('');
        setQueueAhead(null);
      }
      setError('');
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to update conversation.');
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Box sx={{ p: 2, bgcolor: '#254c3d', color: 'white', display: 'flex', justifyContent: 'space-between' }}>
        <Box>
          <Typography fontWeight={800}>Northline support</Typography>
          <Typography variant="caption">AI shopping and human support</Typography>
        </Box>
        <IconButton onClick={onClose} sx={{ color: 'white' }}><Close /></IconButton>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2, bgcolor: '#fafafa' }}>
        {!conversation ? (
          <Stack spacing={2}>
            <Typography>Ask about gear, orders, shipping, or returns.</Typography>
            <Button variant="contained" onClick={startConversation}>Start conversation</Button>
          </Stack>
        ) : (
          <>
            {conversation.status === 'closed' && (
              <Alert severity="info" sx={{ mb: 2 }}>
                This conversation has ended. Start a new conversation to get further support.
              </Alert>
            )}
            {conversation.status === 'waiting' && (
              <Alert severity="info" sx={{ mb: 2 }}>
                Waiting for an agent. {queueAhead === null ? '' : `${queueAhead} ahead of you.`}
              </Alert>
            )}
            {conversation.messages.map(message => (
              <MessageBubble key={message.id} message={message} onClose={onClose} />
            ))}
          </>
        )}
        {error && <Alert severity="warning">{error}</Alert>}
      </Box>

      {conversation?.status !== 'closed' && conversation && (
        <Box sx={{ borderTop: '1px solid #ddd', p: 2 }}>
          {conversation.status === 'ai' && (
            <Button onClick={() => changeStatus('request-human')} fullWidth sx={{ mb: 1 }}>
              Talk to a human
            </Button>
          )}
          <Stack direction="row" spacing={1}>
            <TextField
              fullWidth
              size="small"
              placeholder="Write a message..."
              value={text}
              onChange={event => setText(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
            />
            <IconButton disabled={!text.trim() || sending} onClick={sendMessage}>
              <Send />
            </IconButton>
          </Stack>
          <Button size="small" sx={{ mt: 1 }} onClick={() => changeStatus('close')}>
            End conversation
          </Button>
        </Box>
      )}
      {conversation?.status === 'closed' && (
        <Box sx={{ p: 2 }}>
          <Button fullWidth onClick={() => setConversation(null)}>Start a new conversation</Button>
        </Box>
      )}
    </Box>
  );
}
