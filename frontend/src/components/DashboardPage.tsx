import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Grid,
  Typography,
  Button,
  Box,
  Card,
  CardContent,
  CardActions,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Chip,
  IconButton,
  Avatar,
  Menu,
  LinearProgress,
  alpha,
  Paper,
  Divider,
} from '@mui/material';
import {
  Add as AddIcon,
  Mic as MicIcon,
  CloudUpload as UploadIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Logout as LogoutIcon,
  Person as PersonIcon,
  Settings as SettingsIcon,
  FiberManualRecord as RecordIcon,
  Folder as FolderIcon,
  AccessTime as TimeIcon,
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';
import apiService from '../services/api';
import { Meeting, Organization } from '../types';
import Logo from './Logo';

const DashboardPage: React.FC = () => {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [liveRecordingDialogOpen, setLiveRecordingDialogOpen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [newMeeting, setNewMeeting] = useState({
    title: '',
    description: '',
    language_preference: 'en',
    organization: '',
  });
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  useEffect(() => {
    loadMeetings();
    loadOrganizations();
  }, []);

  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isRecording]);

  const loadMeetings = async () => {
    try {
      const meetingsData = await apiService.getMeetings();
      setMeetings(meetingsData);
    } catch (error) {
      console.error('Failed to load meetings:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadOrganizations = async () => {
    try {
      const orgsData = await apiService.getOrganizations();
      setOrganizations(orgsData);
      if (orgsData.length > 0) {
        setNewMeeting((prev) => ({ ...prev, organization: orgsData[0].id }));
      }
    } catch (error) {
      console.error('Failed to load organizations:', error);
    }
  };

  const handleCreateMeeting = async () => {
    try {
      const meeting = await apiService.createMeeting(newMeeting);
      setDialogOpen(false);
      setNewMeeting({
        title: '',
        description: '',
        language_preference: 'en',
        organization: organizations[0]?.id || '',
      });
      loadMeetings();
      navigate(`/meeting/${meeting.id}`);
    } catch (error) {
      console.error('Failed to create meeting:', error);
    }
  };

  const handleStartLiveRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach((track) => track.stop());
        await handleUploadRecording(audioBlob, `Live Recording - ${new Date().toLocaleString()}`);
      };

      mediaRecorder.start(1000);
      setIsRecording(true);
      setRecordingTime(0);
    } catch (error) {
      console.error('Failed to start recording:', error);
      alert('Failed to access microphone. Please check your permissions.');
    }
  };

  const handleStopLiveRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setLiveRecordingDialogOpen(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleUploadRecording = async (file: Blob | File, title?: string) => {
    if (!organizations[0]) {
      alert('Please create an organization first');
      return;
    }

    try {
      setUploadProgress(10);
      const meeting = await apiService.createMeeting({
        title: title || (file instanceof File ? file.name : 'Uploaded Recording'),
        description: 'Uploaded audio recording',
        language_preference: 'auto',
        organization: organizations[0].id,
      });
      setUploadProgress(30);

      const recording = await apiService.uploadRecording(meeting.id, file);
      setUploadProgress(60);

      // Trigger transcription (may fail if Deepgram API key is not configured)
      try {
        await apiService.transcribeRecording(meeting.id, recording.id);
      } catch (transcribeError) {
        console.warn('Transcription failed (API key may not be configured):', transcribeError);
      }
      setUploadProgress(100);

      setSelectedFile(null);
      setUploadDialogOpen(false);
      setUploadProgress(0);
      loadMeetings();
      navigate(`/meeting/${meeting.id}`);
    } catch (error) {
      console.error('Failed to upload recording:', error);
      alert('Failed to upload recording. Please try again.');
      setUploadProgress(0);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getLanguageLabel = (lang: string) => {
    const langs: Record<string, string> = {
      en: 'English',
      fr: 'French',
      auto: 'Auto-detect',
    };
    return langs[lang] || lang;
  };

  if (loading) {
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
          <Typography sx={{ mt: 2, color: 'text.secondary' }}>Loading...</Typography>
        </Box>
      </Box>
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
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 2 }}>
            <Logo size="small" />
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', display: { xs: 'none', sm: 'block' } }}>
                {user?.first_name || user?.email}
              </Typography>
              <IconButton onClick={(e) => setAnchorEl(e.currentTarget)}>
                <Avatar
                  sx={{
                    width: 40,
                    height: 40,
                    background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                  }}
                >
                  {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase()}
                </Avatar>
              </IconButton>
              <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
                <MenuItem onClick={() => setAnchorEl(null)}>
                  <PersonIcon sx={{ mr: 1 }} /> Profile
                </MenuItem>
                <MenuItem onClick={() => setAnchorEl(null)}>
                  <SettingsIcon sx={{ mr: 1 }} /> Settings
                </MenuItem>
                <Divider />
                <MenuItem onClick={handleLogout}>
                  <LogoutIcon sx={{ mr: 1 }} /> Logout
                </MenuItem>
              </Menu>
            </Box>
          </Box>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ mb: 4 }}>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Welcome back, {user?.first_name || 'there'}!
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Start a new recording or upload existing audio files for transcription
          </Typography>
        </Box>

        <Grid container spacing={3} sx={{ mb: 5 }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card
              sx={{
                height: '100%',
                cursor: 'pointer',
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                color: 'white',
                '&:hover': {
                  transform: 'translateY(-8px)',
                  boxShadow: '0 20px 60px rgba(99, 102, 241, 0.4)',
                },
              }}
              onClick={() => setLiveRecordingDialogOpen(true)}
            >
              <CardContent sx={{ p: 4 }}>
                <Box
                  sx={{
                    width: 64,
                    height: 64,
                    borderRadius: '16px',
                    background: 'rgba(255, 255, 255, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mb: 3,
                  }}
                >
                  <MicIcon sx={{ fontSize: 32 }} />
                </Box>
                <Typography variant="h5" fontWeight={700} gutterBottom>
                  Record Live
                </Typography>
                <Typography variant="body1" sx={{ opacity: 0.9 }}>
                  Start a live recording session. Your audio will be captured and transcribed in real-time.
                </Typography>
              </CardContent>
              <CardActions sx={{ px: 4, pb: 3 }}>
                <Button
                  variant="contained"
                  sx={{
                    background: 'rgba(255, 255, 255, 0.2)',
                    color: 'white',
                    '&:hover': { background: 'rgba(255, 255, 255, 0.3)' },
                  }}
                  startIcon={<PlayIcon />}
                >
                  Start Recording
                </Button>
              </CardActions>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Card
              sx={{
                height: '100%',
                cursor: 'pointer',
                background: 'linear-gradient(135deg, #ec4899 0%, #f472b6 100%)',
                color: 'white',
                '&:hover': {
                  transform: 'translateY(-8px)',
                  boxShadow: '0 20px 60px rgba(236, 72, 153, 0.4)',
                },
              }}
              onClick={() => setUploadDialogOpen(true)}
            >
              <CardContent sx={{ p: 4 }}>
                <Box
                  sx={{
                    width: 64,
                    height: 64,
                    borderRadius: '16px',
                    background: 'rgba(255, 255, 255, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mb: 3,
                  }}
                >
                  <UploadIcon sx={{ fontSize: 32 }} />
                </Box>
                <Typography variant="h5" fontWeight={700} gutterBottom>
                  Upload Recording
                </Typography>
                <Typography variant="body1" sx={{ opacity: 0.9 }}>
                  Upload an existing audio or video file from your device for transcription.
                </Typography>
              </CardContent>
              <CardActions sx={{ px: 4, pb: 3 }}>
                <Button
                  variant="contained"
                  sx={{
                    background: 'rgba(255, 255, 255, 0.2)',
                    color: 'white',
                    '&:hover': { background: 'rgba(255, 255, 255, 0.3)' },
                  }}
                  startIcon={<UploadIcon />}
                >
                  Choose File
                </Button>
              </CardActions>
            </Card>
          </Grid>
        </Grid>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h5" fontWeight={600}>
            Your Meetings
          </Typography>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
            New Meeting
          </Button>
        </Box>

        {meetings.length === 0 ? (
          <Paper
            sx={{
              p: 6,
              textAlign: 'center',
              background: 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
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
                mx: 'auto',
                mb: 3,
              }}
            >
              <FolderIcon sx={{ fontSize: 40, color: 'primary.main' }} />
            </Box>
            <Typography variant="h6" gutterBottom>
              No meetings yet
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Create your first meeting or start a live recording to get started
            </Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
              Create Meeting
            </Button>
          </Paper>
        ) : (
          <Grid container spacing={3}>
            {meetings.map((meeting) => (
              <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={meeting.id}>
                <Card sx={{ height: '100%' }}>
                  <CardContent sx={{ pb: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                      <Typography variant="h6" fontWeight={600} sx={{ flex: 1 }}>
                        {meeting.title}
                      </Typography>
                      <Chip
                        size="small"
                        icon={<RecordIcon sx={{ fontSize: 12 }} />}
                        label="Live"
                        color="success"
                        sx={{ ml: 1, display: meeting.live_sessions?.some((s) => s.status === 'active') ? 'inline-flex' : 'none' }}
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2, minHeight: 40 }}>
                      {meeting.description || 'No description'}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      <Chip size="small" label={getLanguageLabel(meeting.language_preference)} color="primary" variant="outlined" />
                      <Chip size="small" label={meeting.organization_name} variant="outlined" />
                    </Box>
                  </CardContent>
                  <CardActions sx={{ px: 2, pb: 2, pt: 0 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                      <TimeIcon sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
                      <Typography variant="caption" color="text.secondary">
                        {new Date(meeting.created_at).toLocaleDateString()}
                      </Typography>
                    </Box>
                    <Button size="small" variant="contained" onClick={() => navigate(`/meeting/${meeting.id}`)}>
                      Open
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Container>

      <Dialog open={liveRecordingDialogOpen} onClose={() => !isRecording && setLiveRecordingDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ textAlign: 'center', pt: 4 }}>
          <Box
            sx={{
              width: 80,
              height: 80,
              borderRadius: '50%',
              background: isRecording
                ? 'linear-gradient(135deg, #ef4444 0%, #f87171 100%)'
                : 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mx: 'auto',
              mb: 2,
              animation: isRecording ? 'pulse 1.5s infinite' : 'none',
              '@keyframes pulse': {
                '0%': { boxShadow: '0 0 0 0 rgba(239, 68, 68, 0.4)' },
                '70%': { boxShadow: '0 0 0 20px rgba(239, 68, 68, 0)' },
                '100%': { boxShadow: '0 0 0 0 rgba(239, 68, 68, 0)' },
              },
            }}
          >
            <MicIcon sx={{ fontSize: 40, color: 'white' }} />
          </Box>
          {isRecording ? 'Recording in Progress' : 'Live Recording'}
        </DialogTitle>
        <DialogContent sx={{ textAlign: 'center' }}>
          {isRecording ? (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                {formatTime(recordingTime)}
              </Typography>
              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, mb: 2 }}>
                {[...Array(5)].map((_, i) => (
                  <Box
                    key={i}
                    sx={{
                      width: 4,
                      height: 20 + Math.random() * 20,
                      background: 'linear-gradient(to top, #ef4444, #f87171)',
                      borderRadius: 2,
                      animation: 'wave 0.5s ease-in-out infinite',
                      animationDelay: `${i * 0.1}s`,
                      '@keyframes wave': {
                        '0%, 100%': { transform: 'scaleY(0.5)' },
                        '50%': { transform: 'scaleY(1)' },
                      },
                    }}
                  />
                ))}
              </Box>
              <Typography variant="body2" color="text.secondary">
                Speak clearly into your microphone
              </Typography>
            </Box>
          ) : (
            <Typography variant="body1" color="text.secondary">
              Click the button below to start recording. Make sure your microphone is connected and enabled.
            </Typography>
          )}
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'center', pb: 4, gap: 2 }}>
          {isRecording ? (
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                color="error"
                size="large"
                startIcon={<StopIcon />}
                onClick={handleStopLiveRecording}
                sx={{ px: 4 }}
              >
                Stop Recording
              </Button>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button onClick={() => setLiveRecordingDialogOpen(false)}>Cancel</Button>
              <Button variant="contained" size="large" startIcon={<MicIcon />} onClick={handleStartLiveRecording} sx={{ px: 4 }}>
                Start Recording
              </Button>
            </Box>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={uploadDialogOpen} onClose={() => setUploadDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ textAlign: 'center', pt: 4 }}>
          <Box
            sx={{
              width: 80,
              height: 80,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #ec4899 0%, #f472b6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mx: 'auto',
              mb: 2,
            }}
          >
            <UploadIcon sx={{ fontSize: 40, color: 'white' }} />
          </Box>
          Upload Recording
        </DialogTitle>
        <DialogContent>
          <Box
            sx={{
              border: '2px dashed',
              borderColor: selectedFile ? 'primary.main' : 'divider',
              borderRadius: 3,
              p: 4,
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.2s',
              background: selectedFile ? alpha('#6366f1', 0.05) : 'transparent',
              '&:hover': {
                borderColor: 'primary.main',
                background: alpha('#6366f1', 0.05),
              },
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,video/*"
              style={{ display: 'none' }}
              onChange={handleFileSelect}
            />
            {selectedFile ? (
              <Box>
                <Typography variant="h6" gutterBottom>
                  {selectedFile.name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </Typography>
              </Box>
            ) : (
              <Box>
                <UploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Drop your file here or click to browse
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Supports MP3, WAV, M4A, MP4, and more
                </Typography>
              </Box>
            )}
          </Box>
          <Box sx={{ mt: 3, display: uploadProgress > 0 ? 'block' : 'none' }}>
            <LinearProgress variant="determinate" value={uploadProgress} sx={{ borderRadius: 5, height: 8 }} />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
              Uploading... {uploadProgress}%
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'center', pb: 4, gap: 2 }}>
          <Button onClick={() => setUploadDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!selectedFile || uploadProgress > 0}
            onClick={() => selectedFile && handleUploadRecording(selectedFile)}
            sx={{ px: 4 }}
          >
            Upload & Transcribe
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Meeting</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Meeting Title"
            fullWidth
            variant="outlined"
            value={newMeeting.title}
            onChange={(e) => setNewMeeting({ ...newMeeting, title: e.target.value })}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Description"
            fullWidth
            multiline
            rows={3}
            variant="outlined"
            value={newMeeting.description}
            onChange={(e) => setNewMeeting({ ...newMeeting, description: e.target.value })}
            sx={{ mb: 2 }}
          />
          <TextField
            select
            margin="dense"
            label="Organization"
            fullWidth
            variant="outlined"
            value={newMeeting.organization}
            onChange={(e) => setNewMeeting({ ...newMeeting, organization: e.target.value })}
            sx={{ mb: 2 }}
          >
            {organizations.map((org) => (
              <MenuItem key={org.id} value={org.id}>
                {org.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            margin="dense"
            label="Language"
            fullWidth
            variant="outlined"
            value={newMeeting.language_preference}
            onChange={(e) => setNewMeeting({ ...newMeeting, language_preference: e.target.value })}
          >
            <MenuItem value="en">English</MenuItem>
            <MenuItem value="fr">French</MenuItem>
            <MenuItem value="auto">Auto-detect</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateMeeting} variant="contained">
            Create Meeting
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DashboardPage;
