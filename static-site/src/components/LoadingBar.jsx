import React from 'react';
import './LoadingBar.css';

const LoadingBar = ({ duration = '10s' }) => {
  return (
    <div className="loading-bar-container">
      <div className="loading-bar" style={{ animationDuration: duration }}></div>
    </div>
  );
};

export default LoadingBar; 