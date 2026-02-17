import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth'; 

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, initialCheckDone } = useAuth();
  
  console.log('ProtectedRoute - State:', { isAuthenticated, isLoading, initialCheckDone });
  
  // Afficher un loader pendant la vérification
  if (isLoading || !initialCheckDone) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh' 
      }}>
        <div>Chargement...</div> {}
      </div>
    );
  }
  
  // Rediriger vers login si non authentifié
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // Afficher les enfants si authentifié
  return <>{children}</>;
};

export default ProtectedRoute;