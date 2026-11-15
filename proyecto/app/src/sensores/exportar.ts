import { Directory, File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { ErrorParaUsuario } from '@/src/errores';

export * from './formato';

/** Carpeta del teléfono donde viven las grabaciones (documentos de la app). */
export function carpetaGrabaciones(): Directory {
  const dir = new Directory(Paths.document, 'grabaciones');
  if (!dir.exists) dir.create({ intermediates: true });
  return dir;
}

export interface ArchivosGrabacion {
  gps: File; // <base>.csv (el del contrato)
  acel: File; // <base>_acel.csv
  meta: File; // <base>_meta.json (cambios de etiqueta, inicio y fin)
}

export function archivosDe(base: string): ArchivosGrabacion {
  const dir = carpetaGrabaciones();
  return {
    gps: new File(dir, `${base}.csv`),
    acel: new File(dir, `${base}_acel.csv`),
    meta: new File(dir, `${base}_meta.json`),
  };
}

/** Grabaciones guardadas, de la más reciente a la más antigua (solo el CSV principal). */
export function listarGrabaciones(): File[] {
  return carpetaGrabaciones()
    .list()
    .filter((x): x is File => x instanceof File && x.uri.endsWith('.csv') && !x.uri.endsWith('_acel.csv'))
    .sort((a, b) => b.uri.localeCompare(a.uri));
}

/** Abre la hoja de compartir del sistema (correo, Drive, WhatsApp...) con el CSV. */
export async function compartir(archivo: File): Promise<void> {
  if (!(await Sharing.isAvailableAsync())) {
    throw new ErrorParaUsuario('Compartir no está disponible en este dispositivo.');
  }
  await Sharing.shareAsync(archivo.uri, {
    mimeType: 'text/csv',
    UTI: 'public.comma-separated-values-text',
    dialogTitle: 'Compartir grabación',
  });
}
