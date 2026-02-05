import { motion } from "framer-motion";

export const GradientText = ({ 
  children, 
  className = "",
  gradient = "from-[#F2B705] via-[#FFD54F] to-[#F2B705]"
}) => {
  return (
    <motion.span
      className={`bg-gradient-to-r ${gradient} bg-clip-text text-transparent bg-[length:200%_auto] ${className}`}
      animate={{
        backgroundPosition: ["0% center", "200% center"]
      }}
      transition={{
        duration: 5,
        repeat: Infinity,
        ease: "linear"
      }}
    >
      {children}
    </motion.span>
  );
};

export const AnimatedUnderline = ({ 
  children, 
  className = "",
  color = "#F2B705"
}) => {
  return (
    <motion.span 
      className={`relative inline-block ${className}`}
      whileHover="hover"
    >
      {children}
      <motion.span
        className="absolute bottom-0 left-0 h-0.5"
        style={{ backgroundColor: color }}
        initial={{ width: "0%" }}
        variants={{
          hover: { width: "100%" }
        }}
        transition={{ duration: 0.3 }}
      />
    </motion.span>
  );
};
