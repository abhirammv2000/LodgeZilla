// TouristPage.js

import React, { useState, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import TextField from '@mui/material/TextField';
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
import LogoutButton from '../components/LogoutButton';
import { fetchProperties, reserveProperty } from '../services/TouristApi';
import { useAuth } from '../services/AuthContext';
import { isTokenValid } from '../services/jwt';

const TouristPage = () => {
  const [location, setLocation] = useState('');
  const [startDate, setStartDate] = useState(new Date());
  const [endDate, setEndDate] = useState(new Date());
  const [properties, setProperties] = useState([]);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(5);
  const { jwtToken, logout } = useAuth();

  const handleSearch = async () => {
    try {
      const fetchedProperties = await fetchProperties(location, startDate.toISOString().split('T')[0], endDate.toISOString().split('T')[0]);
      setProperties(fetchedProperties);
    } catch (error) {
      console.error('Error fetching properties:', error.message);
    }
  };
  
  useEffect(() => {
    // Previously this only fired when jwtToken was truthy, so a visitor
    // with no token at all (not logged in) never hit the logout/redirect
    // path here; HostPage.js had an equivalent guard for its own route,
    // this one didn't.
    if (jwtToken && !isTokenValid(jwtToken)) {
      logout();
    }
  }, [jwtToken, logout]);

  if (!isTokenValid(jwtToken)) {
    return <Navigate to="/" replace />;
  }

  const handleLocationChange = (e) => {
    setLocation(e.target.value);
  };

  const handleStartDateChange = (date) => {
    setStartDate(date);
  };

  const handleEndDateChange = (date) => {
    setEndDate(date);
  };

  const handleViewDetails = (property) => {
    setSelectedProperty(property);
  };

  const handleReserve = async (propertyId) => {
    try {
      const propertyIdInt = parseInt(propertyId, 10)
      console.log("PropertyID", typeof(propertyId), typeof(propertyIdInt))
      await reserveProperty(
        propertyIdInt,
        startDate.toISOString().split('T')[0],
        endDate.toISOString().split('T')[0],
        jwtToken
      );
      setSelectedProperty(null);
      // Fetch properties again after reservation to update the list
      await handleSearch();
    } catch (error) {
      console.error('Error reserving property:', error.message);
    }
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

  return (
    <div style={{ textAlign: 'center', marginTop: '50px', backgroundColor: '#f0f0f0', height: '100vh' }}>
      <h2>Tourist Page</h2>
      <LogoutButton />
      <div style={{ marginBottom: '20px' }}>
        <TextField
          label="Location"
          variant="outlined"
          value={location}
          onChange={handleLocationChange}
          placeholder="Enter location"
        />

        <TextField
          label="From"
          type="date"
          variant="outlined"
          value={startDate.toISOString().split('T')[0]}
          onChange={(e) => handleStartDateChange(new Date(e.target.value))}
        />

        <TextField
          label="To"
          type="date"
          variant="outlined"
          value={endDate.toISOString().split('T')[0]}
          onChange={(e) => handleEndDateChange(new Date(e.target.value))}
        />

        <Button variant="contained" onClick={handleSearch}>
          Search
        </Button>
      </div>

      <div>
        <h3>Available Properties</h3>
        {properties.length > 0 ? (
          <>
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
          </>
        ) : (
          <p>No properties found. Try adjusting your search criteria.</p>
        )}
        {selectedProperty && (
          <Card style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', overflow: 'auto', maxHeight: '90vh', width: '75%' }}>
            <CardContent>
              <CancelIcon style={{ position: 'absolute', top: '10px', right: '10px', cursor: 'pointer' }} onClick={handleCancel} />
              <h3>{selectedProperty.title}</h3>
              <p><strong>Location:</strong> {selectedProperty.location}</p>
              <p><strong>Rating:</strong> {selectedProperty.rating}</p>
              <p><strong>Summary:</strong> {selectedProperty.summary}</p>
              <p><strong>Price:</strong> {selectedProperty.price}</p>
              <Button variant="contained" onClick={() => handleReserve(selectedProperty.property_id)}>
                Reserve
              </Button>
              <Button variant="contained" style={{ marginLeft: '10px' }} onClick={handleCancel}>
                Cancel
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default TouristPage;
