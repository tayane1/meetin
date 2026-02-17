import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Button,
  Box,
  IconButton,
  Chip,
  List,
  ListItem,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Divider,
  Alert,
  LinearProgress,
  alpha,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Mic as MicIcon,
  Edit as EditIcon,
  Person as PersonIcon,
  ArrowBack as BackIcon,
  FiberManualRecord as RecordIcon,
  GraphicEq as WaveIcon,
} from '@mui/icons-material';
import { MeetingProvider, useMeeting } from '../hooks/useMeeting';
import Logo from './Logo';

const MeetingPage: React.FC = () => {
  const { meetingId } = useParams<{ meetingId: string }>();
  const navigate = useNavigate();

  if (!meetingId) {
    navigate('/dashboard');
    return null;
  }

  return (
    <MeetingProvider meetingId={meetingId}>
      <MeetingPageContent />
    </MeetingProvider>
  );
};

const MeetingPageContent: React.FC = () => {
  const navigate = useNavigate();
  const {
    meeting,
    transcriptSegments,
    speakers,
    isLive,
    connectionStatus,
    isLoading,
    error,
    startLiveSession,
    stopLiveSession,
    updateSpeaker,
    clearError,
  } = useMeeting();

  const [speakerDialogOpen, setSpeakerDialogOpen] = useState(false);
  const [selectedSpeaker, setSelectedSpeaker] = useState<string>('');
  const [speakerDisplayName, setSpeakerDisplayName] = useState('');

  const handleSpeakerEdit = (speakerLabel: string, currentName?: string) => {
    setSelectedSpeaker(speakerLabel);
    setSpeakerDisplayName(currentName || '');
    setSpeakerDialogOpen(true);
  };

  const handleSpeakerSave = async () => {
    try {
      await updateSpeaker(selectedSpeaker, speakerDisplayName);
      setSpeakerDialogOpen(false);
    } catch (error) {
      console.error('Failed to update speaker:', error);
    }
  };

  const formatTime = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'success';
      case 'connecting':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  if (isLoading && !meeting) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
        }}
      >
        <Box sx={{ textAlign: 'center' }}>
          <Logo size="large" />
          <LinearProgress sx={{ mt: 3, width: 200 }} />
        </Box>
      </Box>
    );
  }

  if (!meeting) {
    return (
      <Container sx={{ mt: 4 }}>
        <Alert severity="error">Meeting not found</Alert>
      </Container>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)' }}>
      <Box
        sx={{
          background: 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(0, 0, 0, 0.05)',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <Container maxWidth="xl">
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <IconButton onClick={() => navigate('/dashboard')} sx={{ mr: 1 }}>
                <BackIcon />
              </IconButton>
              <Logo size="small" />
            </Box>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Chip label={connectionStatus} color={getConnectionStatusColor() as any} size="small" variant="outlined" />
              <Chip
                icon={<RecordIcon sx={{ fontSize: 12, animation: 'blink 1s infinite' }} />}
                label="LIVE"
                color="error"
                size="small"
                sx={{
                  display: isLive ? 'inline-flex' : 'none',
                  '@keyframes blink': {
                    '0%, 100%': { opacity: 1 },
                    '50%': { opacity: 0.5 },
                  },
                }}
              />
            </Box>
          </Box>
        </Container>
      </Box>

      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Alert severity="error" sx={{ mb: 3, borderRadius: 2, display: error ? 'flex' : 'none' }} onClose={clearError}>
          {error}
        </Alert>

        <Box sx={{ mb: 4 }}>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            {meeting.title}
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {meeting.description || 'No description'}
          </Typography>
        </Box>

        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Paper
              sx={{
                p: 3,
                mb: 3,
                background: isLive
                  ? 'linear-gradient(135deg, #ef4444 0%, #f87171 100%)'
                  : 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                color: 'white',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    borderRadius: '12px',
                    background: 'rgba(255, 255, 255, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <MicIcon />
                </Box>
                <Typography variant="h6" fontWeight={600}>
                  {isLive ? 'Recording...' : 'Live Session'}
                </Typography>
              </Box>

              <Box sx={{ display: isLive ? 'flex' : 'none', justifyContent: 'center', gap: 1, mb: 3 }}>
                {[...Array(7)].map((_, i) => (
                  <Box
                    key={i}
                    sx={{
                      width: 4,
                      height: 24,
                      background: 'rgba(255, 255, 255, 0.8)',
                      borderRadius: 2,
                      animation: 'wave 0.5s ease-in-out infinite',
                      animationDelay: `${i * 0.1}s`,
                      '@keyframes wave': {
                        '0%, 100%': { transform: 'scaleY(0.4)' },
                        '50%': { transform: 'scaleY(1)' },
                      },
                    }}
                  />
                ))}
              </Box>

              {!isLive ? (
                <Button
                  fullWidth
                  variant="contained"
                  size="large"
                  startIcon={<StartIcon />}
                  onClick={() => startLiveSession()}
                  disabled={connectionStatus === 'connecting'}
                  sx={{
                    background: 'rgba(255, 255, 255, 0.2)',
                    color: 'white',
                    '&:hover': { background: 'rgba(255, 255, 255, 0.3)' },
                  }}
                >
                  Start Transcription
                </Button>
              ) : (
                <Button
                  fullWidth
                  variant="contained"
                  size="large"
                  startIcon={<StopIcon />}
                  onClick={stopLiveSession}
                  sx={{
                    background: 'rgba(255, 255, 255, 0.2)',
                    color: 'white',
                    '&:hover': { background: 'rgba(255, 255, 255, 0.3)' },
                  }}
                >
                  Stop Recording
                </Button>
              )}
            </Paper>

            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Speakers
              </Typography>
              {speakers.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No speakers detected yet
                </Typography>
              ) : (
                <List dense disablePadding>
                  {speakers.map((speaker, index) => (
                    <React.Fragment key={speaker.id}>
                      <ListItem
                        disablePadding
                        sx={{ py: 1 }}
                        secondaryAction={
                          <IconButton size="small" onClick={() => handleSpeakerEdit(speaker.label, speaker.display_name)}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        }
                      >
                        <Box
                          sx={{
                            width: 36,
                            height: 36,
                            borderRadius: '10px',
                            background: `linear-gradient(135deg, ${
                              ['#6366f1', '#ec4899', '#10b981', '#f59e0b'][index % 4]
                            } 0%, ${['#8b5cf6', '#f472b6', '#34d399', '#fbbf24'][index % 4]} 100%)`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            mr: 2,
                            color: 'white',
                            fontSize: 14,
                            fontWeight: 600,
                          }}
                        >
                          {(speaker.display_name || speaker.label)[0].toUpperCase()}
                        </Box>
                        <ListItemText
                          primary={speaker.display_name || speaker.label}
                          secondary={speaker.display_name ? speaker.label : null}
                        />
                      </ListItem>
                      <Divider sx={{ display: index < speakers.length - 1 ? 'block' : 'none' }} />
                    </React.Fragment>
                  ))}
                </List>
              )}
            </Paper>
          </Grid>

          <Grid size={{ xs: 12, md: 8 }}>
            <Paper sx={{ p: 3, height: 'calc(100vh - 250px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Live Transcript
              </Typography>
              
              <Box sx={{ flex: 1, overflow: 'auto', mt: 2 }}>
                {transcriptSegments.length === 0 ? (
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      height: '100%',
                      textAlign: 'center',
                    }}
                  >
                    <Box
                      sx={{
                        width: 80,
                        height: 80,
                        borderRadius: '20px',
                        background: alpha('#6366f1', 0.1),
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mb: 3,
                      }}
                    >
                      <WaveIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                    </Box>
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                      {isLive ? 'Listening for audio...' : 'No transcript yet'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {isLive ? 'Start speaking and your words will appear here' : 'Start transcription to see live transcript'}
                    </Typography>
                  </Box>
                ) : (
                  <List disablePadding>
                    {transcriptSegments.map((segment, index) => (
                      <ListItem
                        key={segment.id || index}
                        sx={{
                          flexDirection: 'column',
                          alignItems: 'flex-start',
                          py: 2,
                          px: 0,
                          borderBottom: index < transcriptSegments.length - 1 ? '1px solid' : 'none',
                          borderColor: 'divider',
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, width: '100%' }}>
                          <Chip
                            size="small"
                            label={segment.speaker_display_name || segment.speaker_label}
                            sx={{
                              background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                              color: 'white',
                              fontWeight: 500,
                              mr: 1,
                            }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {formatTime(segment.start_ms)}
                          </Typography>
                          <Chip
                            size="small"
                            label="Processing"
                            sx={{ ml: 'auto', fontSize: 10, display: !segment.is_final ? 'inline-flex' : 'none' }}
                            variant="outlined"
                          />
                        </Box>
                        <Typography variant="body1" sx={{ lineHeight: 1.8 }}>
                          {segment.text}
                        </Typography>
                      </ListItem>
                    ))}
                  </List>
                )}
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>

      <Dialog open={speakerDialogOpen} onClose={() => setSpeakerDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ textAlign: 'center', pt: 4 }}>
          <Box
            sx={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mx: 'auto',
              mb: 2,
            }}
          >
            <PersonIcon sx={{ fontSize: 32, color: 'white' }} />
          </Box>
          Edit Speaker Name
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Speaker Name"
            fullWidth
            variant="outlined"
            value={speakerDisplayName}
            onChange={(e) => setSpeakerDisplayName(e.target.value)}
            placeholder={selectedSpeaker}
          />
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'center', pb: 4, gap: 2 }}>
          <Button onClick={() => setSpeakerDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSpeakerSave} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MeetingPage;
