import { API_BASE_URL } from './config';

const BASE_URL = `${API_BASE_URL}/listings`;

export const getProperties = async (userId, token) => {
    try {
      const response = await fetch(`${BASE_URL}/list/${userId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
  
      if (response.ok) {
        const data = await response.json();
        return data;
      } else {
        console.error('Failed to fetch properties:', response.status);
        throw new Error('Failed to fetch properties');
      }
    } catch (error) {
      console.error('Error fetching properties:', error.message);
      throw new Error('Error fetching properties');
    }
  };

export const addProperty = async (propertyData, jwtToken) => {
    const apiUrl = `${BASE_URL}/add`;
  
    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${jwtToken}`,
        },
        body: JSON.stringify(propertyData),
      });
  
      if (!response.ok) {
        throw new Error(`Error: ${response.status} - ${response.statusText}`);
      }
  
      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Error adding property:', error.message);
      throw error;
    }
  };