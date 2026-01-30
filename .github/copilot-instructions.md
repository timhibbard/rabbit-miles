# GitHub Copilot Instructions for RabbitMiles

## Backend Structure

The `backend/` folder contains AWS Lambda function code that represents API endpoints for the RabbitMiles application.

### Key Points

- **Location**: All backend files are located in the `backend/` folder
- **Runtime**: Each subdirectory in `backend/` contains a Python-based AWS Lambda function
- **Purpose**: These Lambda functions serve as API endpoints running on AWS Lambda
- **Structure**: Each Lambda function is in its own subdirectory with a `lambda_function.py` file containing a `handler()` function

### Backend Endpoints

The backend includes the following API endpoints:

- `auth_start/` - Initiates OAuth flow with Strava
- `auth_callback/` - Handles OAuth callback from Strava
- `auth_disconnect/` - Disconnects Strava integration
- `me/` - Returns authenticated user information

### Development Notes

- Backend code is deployed to AWS Lambda and accessible via API Gateway
- The frontend (React SPA) makes API calls to these Lambda endpoints
- All authentication uses secure httpOnly cookies
- Database operations use AWS RDS Data API with Aurora Serverless
