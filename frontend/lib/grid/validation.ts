export const getValidationStatus = (fieldErrors: Record<string, string>, field: string) => {
  return fieldErrors[field] ? "invalid" : "valid";
};

export const getValidationError = (fieldErrors: Record<string, string>, field: string) => {
  return fieldErrors[field] ? { message: fieldErrors[field] } : undefined;
};
