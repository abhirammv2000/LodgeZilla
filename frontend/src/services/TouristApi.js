import { API_BASE_URL } from './config';

const BASE_URL = `${API_BASE_URL}/bookings`;

const fetchProperties = async (destination, fromDate, toDate) => {
  try {
    const queryParams = new URLSearchParams({
      destination,
      from_date: fromDate,
      to_date: toDate,
    });

    const response = await fetch(`${BASE_URL}/search?${queryParams}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Error: ${response.status} - ${response.statusText}`);
    }

    const properties = await response.json();
    return properties;
  } catch (error) {
    console.error('Error fetching properties:', error.message);
    throw error;
  }
};

const reserveProperty = async (propertyId, startDate, endDate, jwtToken) => {
  const url = `${BASE_URL}/reserve/${propertyId}`;

  const requestBody = {
    start_date: startDate,
    end_date: endDate,
  };

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + jwtToken
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    const responseData = await response.json();
    return responseData;
  } catch (error) {
    console.error('Error in reserveProperty API call:', error.message);
    throw error;
  }
};

export { fetchProperties, reserveProperty };
