import { motion } from "framer-motion";

export const FloatingElement = ({ 
  children, 
  duration = 3,
  y = 10,
  className = "" 
}) => {
  return (
    <motion.div
      animate={{
        y: [0, -y, 0],
      }}
      transition={{
        duration,
        repeat: Infinity,
        ease: "easeInOut"
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

export const FloatingShape = ({ 
  color = "rgba(242, 183, 5, 0.1)",
  size = 200,
  top,
  left,
  right,
  bottom,
  delay = 0
}) => {
  return (
    <motion.div
      className="absolute rounded-full pointer-events-none"
      style={{
        backgroundColor: color,
        width: size,
        height: size,
        top,
        left,
        right,
        bottom,
      }}
      animate={{
        y: [0, -30, 0],
        x: [0, 15, 0],
        scale: [1, 1.1, 1],
      }}
      transition={{
        duration: 6,
        delay,
        repeat: Infinity,
        ease: "easeInOut"
      }}
    />
  );
};

export const PulseRing = ({ 
  children, 
  className = "",
  ringColor = "rgba(242, 183, 5, 0.4)"
}) => {
  return (
    <div className={`relative ${className}`}>
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{ backgroundColor: ringColor }}
        animate={{
          scale: [1, 1.5, 1],
          opacity: [0.5, 0, 0.5]
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "easeOut"
        }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
};

export const ShimmerEffect = ({ children, className = "" }) => {
  return (
    <div className={`relative overflow-hidden ${className}`}>
      <motion.div
        className="absolute inset-0 z-10"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent)",
        }}
        animate={{
          x: ["-100%", "100%"]
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "linear",
          repeatDelay: 3
        }}
      />
      {children}
    </div>
  );
};
