import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Container, Grid, Paper, Stack, TextField, Typography,
} from '@mui/material';

import api from '../api';

export default function SupportWorkspace() {
  const [queue, setQueue] = useState([]);
  const [assigned, setAssigned] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [conversation, setConversation] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      const [queueResponse, assignedResponse] = await Promise.all([
        api.get('/support/queue'),
        api.get('/support/conversations'),
      ]);
      setQueue(queueResponse.data);
      setAssigned(assignedResponse.data.filter(item => item.status === 'active'));

      try {
        const approvalResponse = await api.get('/support/approvals');
        setApprovals(approvalResponse.data.filter(item => item.status === 'pending'));
      } catch {
        setApprovals([]);
      }

      if (conversation?.id) {
        const { data } = await api.get(`/support/conversations/${conversation.id}`);
        setConversation(data);
      }
      setError('');
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Staff access required.');
    }
  }, [conversation?.id]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function claim(id) {
    try {
      const { data } = await api.post(`/support/conversations/${id}/claim`);
      setConversation(data);
      await refresh();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to claim chat.');
    }
  }

  async function reply() {
    if (!conversation || !message.trim()) return;
    try {
      const { data } = await api.post(
        `/support/conversations/${conversation.id}/messages`,
        { content: message.trim() },
      );
      setConversation(data);
      setMessage('');
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to send reply.');
    }
  }

  async function review(id, approved) {
    try {
      await api.post(`/support/approvals/${id}/decision`, { approved });
      await refresh();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Manager approval required.');
    }
  }

  return (
    <Container sx={{ py: 5 }}>
      <Typography variant="h4" fontWeight={800}>Support workspace</Typography>
      <Typography color="text.secondary">
        Assigned support agents handle chats. Managers review approvals.
      </Typography>
      {error && <Alert severity="warning" sx={{ mt: 2 }}>{error}</Alert>}

      <Grid container spacing={3} sx={{ mt: 2 }}>
        <Grid item xs={12} md={4}>
          <Typography variant="h6">Waiting queue</Typography>
          {queue.map(item => (
            <Paper key={item.id} sx={{ p: 2, my: 1 }}>
              <Typography>Conversation #{item.id}</Typography>
              <Button onClick={() => claim(item.id)}>Claim chat</Button>
            </Paper>
          ))}
          {!queue.length && <Typography>No waiting conversations.</Typography>}

          <Typography variant="h6" sx={{ mt: 3 }}>Active conversations</Typography>
          {assigned.map(item => (
            <Paper key={item.id} sx={{ p: 2, my: 1 }}>
              <Typography>Conversation #{item.id}</Typography>
              <Button onClick={() => setConversation(item)}>Open</Button>
            </Paper>
          ))}
        </Grid>

        <Grid item xs={12} md={8}>
          {approvals.map(item => (
            <Alert key={item.id} severity="warning" sx={{ mb: 2 }}>
              <Typography fontWeight={700}>Approval #{item.id}</Typography>
              <Typography>{item.reason}</Typography>
              <Button onClick={() => review(item.id, true)}>Approve review</Button>
              <Button color="error" onClick={() => review(item.id, false)}>Reject</Button>
            </Alert>
          ))}

          {conversation ? (
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6">
                Conversation #{conversation.id} · {conversation.status}
              </Typography>
              <Box sx={{ height: 320, overflow: 'auto', my: 2 }}>
                {conversation.messages.map(item => (
                  <Box
                    key={item.id}
                    sx={{ display: 'flex', justifyContent: item.sender === 'agent' ? 'flex-end' : 'flex-start', my: 1 }}
                  >
                    <Paper sx={{ p: 1.5, maxWidth: '82%' }}>
                      <Typography variant="caption">{item.sender}</Typography>
                      <Typography sx={{ whiteSpace: 'pre-wrap' }}>{item.content}</Typography>
                    </Paper>
                  </Box>
                ))}
              </Box>
              <Stack direction="row" spacing={1}>
                <TextField
                  fullWidth
                  value={message}
                  onChange={event => setMessage(event.target.value)}
                  placeholder="Reply to customer"
                />
                <Button variant="contained" onClick={reply}>Send</Button>
              </Stack>
              <Button
                sx={{ mt: 2 }}
                onClick={async () => {
                  await api.post(`/support/conversations/${conversation.id}/close`);
                  setConversation(null);
                  refresh();
                }}
              >
                Close chat
              </Button>
            </Paper>
          ) : (
            <Typography>Select a conversation to respond.</Typography>
          )}
        </Grid>
      </Grid>
    </Container>
  );
}
