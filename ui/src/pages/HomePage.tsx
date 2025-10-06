const HomePage = () => {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-slate-50 text-slate-900">
      <h1 className="text-5xl font-bold tracking-tight">ThreadWise</h1>
      <p className="mt-4 text-lg text-slate-600">
        Welcome to your React + TailwindCSS project scaffold.
      </p>
      <div className="mt-8 flex gap-4">
        <a
          className="rounded-md bg-slate-900 px-5 py-2 text-sm font-medium text-white shadow hover:bg-slate-700"
          href="https://react.dev"
          target="_blank"
          rel="noreferrer"
        >
          React docs
        </a>
        <a
          className="rounded-md border border-slate-300 px-5 py-2 text-sm font-medium text-slate-700 shadow-sm hover:border-slate-400"
          href="https://tailwindcss.com/docs"
          target="_blank"
          rel="noreferrer"
        >
          Tailwind docs
        </a>
      </div>
    </main>
  );
};

export default HomePage;
