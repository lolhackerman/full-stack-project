# ThreadWise TypeScript API

Simple Express server written in TypeScript. Provides a starter structure for building out the ThreadWise API.

## Prerequisites

- Node.js 18+
- npm 9+

## Getting Started

Install dependencies:

```bash
npm install
```

### Development

Launch the app with hot reloading:

```bash
npm run dev
```

### Production Build

Compile TypeScript to JavaScript:

```bash
npm run build
```

Start the compiled server:

```bash
npm start
```

The server listens on `http://localhost:3000` by default and responds with a JSON greeting at the root route `/`.

## Project Structure

- `src/index.ts` – Express application entry point.
- `dist/` – Compiled JavaScript output (generated after `npm run build`).
- `tsconfig.json` – TypeScript compiler configuration.

## Environment Variables

- `PORT` – Optional. Overrides the default port `3000`.

## Additional Scripts

- `npm run lint` – _not configured_. Add ESLint when ready.
- `npm test` – _not configured_. Add tests as the API evolves.

