// Placa ecuatoriana del contrato (§4.3): 3 letras, guion opcional y 3 o 4 dígitos.
export const PATRON_PLACA = /^[A-Z]{3}-?\d{3,4}$/;

/** Lo que escribe el usuario, en mayúsculas y sin espacios (para el TextInput). */
export function normalizarPlaca(texto: string): string {
  return texto.toUpperCase().replace(/\s+/g, '');
}

export function esPlacaValida(placa: string): boolean {
  return PATRON_PLACA.test(placa);
}
