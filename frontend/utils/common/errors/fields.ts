// utils/common/errors/fields.ts

export const removeFieldError = (fieldErrors: Record<string, string>, field: string): Record<string, string> => {
  const newErrors = { ...fieldErrors };
  delete newErrors[field];
  return newErrors;
};
