export const PASSWORD_POLICY_MESSAGE =
  "Password must be at least 10 characters and include uppercase, lowercase, number, and symbol.";

export function validatePasswordPolicy(password: string) {
  if (password.length < 10) {
    return {
      valid: false,
      message: PASSWORD_POLICY_MESSAGE,
    };
  }

  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSymbol = /[^A-Za-z0-9]/.test(password);

  if (!hasUppercase || !hasLowercase || !hasNumber || !hasSymbol) {
    return {
      valid: false,
      message: PASSWORD_POLICY_MESSAGE,
    };
  }

  return {
    valid: true,
    message: "",
  };
}
