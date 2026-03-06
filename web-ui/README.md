# CodeKnowl Web UI

Admin UI and non-engineer access interface for CodeKnowl.

## Why this exists

This React application provides:
- Admin interface for repository lifecycle management
- Indexing status monitoring for operators  
- Q&A interface with citations for non-engineers
- Authentication and authorization integration

## Features

### Repository Management
- Add/remove repositories
- View repository status and indexing history
- Trigger reindexing operations
- Monitor indexing progress

### Q&A Interface
- Ask questions about code with AI-powered answers
- View citations with file locations and snippets
- Select specific repositories for targeted queries
- Streaming responses for real-time interaction

### Indexing Monitoring
- View all indexing jobs and their status
- Monitor progress of running jobs
- Track job history and performance
- Error tracking and debugging

### Authentication
- Secure login with backend integration
- Role-based access control
- Session management

## Development

### Prerequisites
- Node.js 18+
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm run test

# Lint code
npm run lint
```

### Environment Variables

Create a `.env.local` file:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Architecture

### Tech Stack
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **React Router** - Navigation
- **React Query** - Data fetching
- **Axios** - HTTP client
- **Vite** - Build tool

### Project Structure
```
src/
├── components/     # Reusable UI components
├── pages/         # Page components
├── hooks/         # Custom React hooks
├── types/         # TypeScript type definitions
├── utils/         # Utility functions
└── App.tsx        # Main application component
```

## Integration with Backend

The web UI integrates with the CodeKnowl backend API:
- Authentication via `/auth/*` endpoints
- Repository management via `/repos/*` endpoints
- Q&A via `/qa/*` endpoints
- Indexing status via `/jobs/*` endpoints

## Deployment

### Docker Deployment

```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Kubernetes Deployment

The web UI can be deployed as a static site served by nginx or any web server, configured to proxy API requests to the backend.

## Compliance

- ✅ ITD-21: React frontend technology
- ✅ PRD Milestone 9: Admin UI + non-engineer access
- ✅ Architecture & Design: Admin API integration
- ✅ Definition of Done: Tests and documentation
- ✅ OSS packaging: Source code only
