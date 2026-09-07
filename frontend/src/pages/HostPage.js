// HostPage.js

import React, { useState, useEffect, useCallback } from 'react';
import { Navigate } from 'react-router-dom';
import LogoutButton from "../components/LogoutButton";
import { useAuth } from '../services/AuthContext';
import { getProperties, addProperty } from '../services/HostApi';
import { jwtDecode } from 'jwt-decode';
import Button from '@mui/material/Button';
import Table from '@mui/material/Table';
import TableHead from '@mui/material/TableHead';
import TableBody from '@mui/material/TableBody';
import TableRow from '@mui/material/TableRow';
import TableCell from '@mui/material/TableCell';
import TablePagination from '@mui/material/TablePagination';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CancelIcon from '@mui/icons-material/Cancel';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';

const HostPage = () => {
  const [showForm, setShowForm] = useState(false);
  const [properties, setProperties] = useState([]);
  const [propertyName, setPropertyName] = useState('');
  const [propertyLocation, setPropertyLocation] = useState('');
  const [summaryValue, setSummaryValue] = useState('');
  const [priceValue, setPriceValue] = useState('');
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(5);
  const { jwtToken } = useAuth();

  // jwtDecode throws on a missing or malformed token, which would take the
  // whole page down; fall back to sending the visitor to the login screen.
  let hostId = null;
  try {
    hostId = jwtToken ? jwtDecode(jwtToken).sub : null;
  } catch (error) {
    hostId = null;
  }

  const fetchProperties = useCallback(async () => {
    if (!hostId) {
      return;
    }
    try {
      const dataAsString = await getProperties(hostId, jwtToken);
      setProperties(JSON.parse(dataAsString));
    } catch (error) {
      console.error('Error fetching properties:', error.message);
    }
  }, [hostId, jwtToken]);

  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  const handlePropertyNameChange = (e) => {
    setPropertyName(e.target.value);
  };

  const handlePropertyLocationChange = (e) => {
    setPropertyLocation(e.target.value);
  };

  const handleAddProperty = async () => {
    try {
      // Prepare the property data from the form
      const newPropertyData = {
        property_id: Math.floor(Date.now() / 1000),
        title: propertyName,
        location: propertyLocation,
        rating: 0,
        summary: summaryValue,
        price: priceValue,
        booking_history: [],
        host: hostId
      };

      // Make the API call to add the property
      const newProperty = await addProperty(newPropertyData, jwtToken);

      // Update the list of properties
      setProperties([...properties, newProperty]);

      // Clear the input fields and hide the form after adding the property
      setPropertyName('');
      setPropertyLocation('');
      setSummaryValue('');
      setPriceValue('');
      setShowForm(false);
    } catch (error) {
      // Handle errors as needed
      console.error('Error adding property:', error.message);
    }
  };

  const handleCreatePropertyClick = () => {
    setShowForm(true);
  };

  const handleCancelProperty = () => {
    setPropertyName('');
    setPropertyLocation('');
    setSummaryValue('');
    setPriceValue('');
    setShowForm(false);
  };

  const handleViewDetails = (property) => {
    setSelectedProperty(property);
  };

  const handleCancel = () => {
    setSelectedProperty(null);
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const getPaginatedData = () => {
    const startIndex = page * rowsPerPage;
    const endIndex = startIndex + rowsPerPage;
    return properties.slice(startIndex, endIndex);
  };

  if (!hostId) {
    return <Navigate to="/" replace />;
  }

  return (
    <div style={{ textAlign: 'center', marginTop: '50px', backgroundColor: '#eee', height: '100vh' }}>
      <h2>Host Page</h2>
      <LogoutButton />
      {properties.length > 0 ? (
        <div>
          <h3>Available Properties</h3>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Location</TableCell>
                <TableCell>Rating</TableCell>
                <TableCell>Price</TableCell>
                <TableCell>View</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {getPaginatedData().map((property) => (
                <TableRow key={property.property_id}>
                  <TableCell>{property.title}</TableCell>
                  <TableCell>{property.location}</TableCell>
                  <TableCell>{property.rating}</TableCell>
                  <TableCell>{property.price}</TableCell>
                  <TableCell>
                    <Button variant="contained" onClick={() => handleViewDetails(property)}>
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            rowsPerPageOptions={[5, 10, 25]}
            component="div"
            count={properties.length}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
          {selectedProperty && (
            <Card style={{ 
              position: 'fixed', 
              top: '50%', 
              left: '50%', 
              transform: 'translate(-50%, -50%)', 
              overflow: 'auto', 
              maxHeight: '90vh', 
              width: '75%', 
              zIndex: 1000,  // Set a higher z-index for the card
            }}>              
              <CardContent>
                <CancelIcon style={{ position: 'absolute', top: '10px', right: '10px', cursor: 'pointer' }} onClick={handleCancel} />
                <h3>{selectedProperty.title}</h3>
                <p><strong>Location:</strong> {selectedProperty.location}</p>
                <p><strong>Rating:</strong> {selectedProperty.rating}</p>
                <p><strong>Summary:</strong> {selectedProperty.summary}</p>
                <p><strong>Price:</strong> {selectedProperty.price}</p>
              </CardContent>
            </Card>
          )}
        </div>
      ) : (
        <p>Ohh wow! Such empty. Why not create a property?</p>
      )}

      {showForm ? (
        <Card style={{ maxWidth: '600px', margin: '20px auto', padding: '20px' }}>
          <CardContent>
            <h3>Create Property</h3>
            <form>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <TextField
                  label="Property Name"
                  variant="outlined"
                  value={propertyName}
                  onChange={handlePropertyNameChange}
                />
                <TextField
                  label="Property Location"
                  variant="outlined"
                  value={propertyLocation}
                  onChange={handlePropertyLocationChange}
                />
                <TextField
                  label="Summary"
                  variant="outlined"
                  value={summaryValue}
                  onChange={(e) => setSummaryValue(e.target.value)}
                />
                <TextField
                  label="Price"
                  variant="outlined"
                  value={priceValue}
                  onChange={(e) => setPriceValue(e.target.value)}
                />
                <Button variant="contained" onClick={handleAddProperty} sx={{ alignSelf: 'flex-end' }}>
                  Add Property
                </Button>
                <Button variant="contained" onClick={handleCancelProperty} sx={{ alignSelf: 'flex-end', mt: 1 }}>
                  Cancel
                </Button>
              </Box>
            </form>
          </CardContent>
        </Card>
      ) : (
        <Button variant="contained" onClick={handleCreatePropertyClick} sx={{ marginTop: '20px' }}>
          Create Property
        </Button>
      )}
    </div>
  );
};

export default HostPage;
