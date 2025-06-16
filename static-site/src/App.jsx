import React from 'react';
import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage.jsx';
import WordsPage from './pages/WordsPage.jsx';
import ArticlePage from './pages/ArticlePage.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/learn" element={<WordsPage />} />
      <Route path="/article" element={<ArticlePage />} />
    </Routes>
  );
}
