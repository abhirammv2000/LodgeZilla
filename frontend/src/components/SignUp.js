import React, { useState } from 'react';
import {createUser} from '../services/UserApi'
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';

const Signup = ({ onCancel, onSignup }) => {
  const [name, setName] = useState('');
  const [password, setpassword] = useState('');
  const [userType, setUserType] = useState('tourist'); 

  const handleNameChange = (e) => {
    setName(e.target.value);
  };

  const handlepasswordChange = (e) => {
    setpassword(e.target.value);
  };

  const handleUserTypeChange = (e) => {
    setUserType(e.target.value);
  };

  const handleCreate = async () => {
    try {
      const userData = {
        user_id: Math.floor(Date.now() / 1000),
        name,
        password,
        userType,
        trips: {}
      };

      await createUser(userData);

      // Call the onSignup function passed from the parent (Login) component,
      // handing back the credentials just created so the login form can be
      // pre-filled instead of making the user retype what they just entered.
      onSignup({ name, password });
    } catch (error) {
      console.error('Error during user creation:', error);
    }
  };

  return (
    <div>
      <h2>User Sign Up</h2>
      <form>
        <div>
        <TextField
          label="Name"
          variant="outlined"
          value={name}
          onChange={handleNameChange}
          placeholder="Enter your name"
        />
        </div>
        <div>
        <TextField
          label="Password"
          variant="outlined"
          value={password}
          onChange={handlepasswordChange}
          placeholder="Enter Password"
        />
        </div>
        <div>
          <Select value={userType} onChange={handleUserTypeChange} variant="outlined" style={{marginTop: "10px", width: "225px"}}>
            <MenuItem value="tourist">Tourist</MenuItem>
            <MenuItem value="host">Host</MenuItem>
          </Select>
        </div>
        <div style={{ marginTop: '20px'}}>
          <Button type="button" onClick={handleCreate}>
            Create
          </Button>
          <Button type="button" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
};

export default Signup;
