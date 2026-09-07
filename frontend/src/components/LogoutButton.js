// LogoutButton.js

import React from 'react';
import Button from '@mui/material/Button';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../services/AuthContext';

const LogoutButton = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <Button onClick={handleLogout} style={{ position: 'absolute', top: '10px', right: '10px' }}>
      Logout
    </Button>
  );
};

export default LogoutButton;
