using System.Globalization;
using System.Text.Json;
using Microsoft.AnalysisServices.AdomdClient;
using Microsoft.AnalysisServices.Tabular;

/// <summary>
/// Trabajo contra el modelo abierto en Power BI Desktop. Desktop arranca un Analysis Services local en un puerto que
/// cambia cada vez (está en el fichero msmdsrv.port.txt de su carpeta de trabajo); con él se puede refrescar el modelo y
/// consultarlo con DAX como haría un visual.
/// </summary>
static class Desktop
{
    /// <summary>Refresca todas las tablas leyendo los Parquet de la carpeta del parámetro CarpetaDeDatos.</summary>
    public static int Refrescar(int puerto)
    {
        using var servidor = new Server();
        servidor.Connect($"Data Source=localhost:{puerto}");
        var modelo = servidor.Databases[0].Model;
        Console.WriteLine($"Refrescando {modelo.Tables.Count} tablas en localhost:{puerto}...");
        modelo.RequestRefresh(RefreshType.Full);
        modelo.SaveChanges();
        foreach (var tabla in modelo.Tables.Where(t => t.CalculationGroup is null))
        {
            Console.WriteLine($"  {tabla.Name}: {Filas(puerto, tabla.Name):N0} filas");
        }
        return 0;
    }

    /// <summary>
    /// Evalúa cada medida de las cifras de control con DAX y la compara con el valor esperado. Sale con 1 si alguna
    /// no coincide.
    /// </summary>
    public static int Comparar(int puerto, string ficheroDeCifras)
    {
        using var documento = JsonDocument.Parse(File.ReadAllText(ficheroDeCifras));
        var fallos = 0;
        using var conexion = new AdomdConnection($"Data Source=localhost:{puerto}");
        conexion.Open();

        foreach (var medida in documento.RootElement.GetProperty("medidas").EnumerateObject())
        {
            var dax = $"EVALUATE ROW(\"v\", [{medida.Name.Replace("]", "]]")}])";
            var obtenido = Valor(conexion, dax);
            var esperado = medida.Value.ValueKind == JsonValueKind.Null ? (double?)null : medida.Value.GetDouble();
            var bien = Iguales(esperado, obtenido);
            fallos += bien ? 0 : 1;
            Console.WriteLine($"{(bien ? "ok " : "MAL")} [{medida.Name}]: esperado {Texto(esperado)}, Power BI {Texto(obtenido)}");
        }

        foreach (var desglose in documento.RootElement.GetProperty("desgloses").EnumerateArray())
        {
            var columna = desglose.GetProperty("columna").GetString()!;
            var filas = new Dictionary<string, double?>();
            using (var comando = new AdomdCommand($"EVALUATE SUMMARIZECOLUMNS({columna}, \"n\", [Licitaciones])", conexion))
            using (var lector = comando.ExecuteReader())
            {
                while (lector.Read())
                {
                    filas[Convert.ToString(lector.GetValue(0), CultureInfo.InvariantCulture) ?? ""] =
                        lector.IsDBNull(1) ? null : Convert.ToDouble(lector.GetValue(1), CultureInfo.InvariantCulture);
                }
            }
            foreach (var fila in desglose.GetProperty("filas").EnumerateArray())
            {
                var clave = fila[0].ToString();
                var esperado = fila[1].GetDouble();
                filas.TryGetValue(clave, out var obtenido);
                var bien = Iguales(esperado, obtenido);
                fallos += bien ? 0 : 1;
                Console.WriteLine($"{(bien ? "ok " : "MAL")} {columna} = {clave}: esperado {Texto(esperado)}, Power BI {Texto(obtenido)}");
            }
        }

        Console.WriteLine(fallos == 0 ? "Todas las cifras coinciden." : $"{fallos} cifras no coinciden.");
        return fallos == 0 ? 0 : 1;
    }

    static long Filas(int puerto, string tabla)
    {
        using var conexion = new AdomdConnection($"Data Source=localhost:{puerto}");
        conexion.Open();
        return Convert.ToInt64(Valor(conexion, $"EVALUATE ROW(\"n\", COUNTROWS('{tabla.Replace("'", "''")}'))") ?? 0);
    }

    static double? Valor(AdomdConnection conexion, string dax)
    {
        using var comando = new AdomdCommand(dax, conexion);
        using var lector = comando.ExecuteReader();
        lector.Read();
        return lector.IsDBNull(0) ? null : Convert.ToDouble(lector.GetValue(0), CultureInfo.InvariantCulture);
    }

    /// <summary>Iguales salvo redondeo: los importes son decimales fijos en Power BI y dobles en DuckDB.</summary>
    static bool Iguales(double? a, double? b) =>
        a is null || b is null ? a is null && b is null : Math.Abs(a.Value - b.Value) <= 1e-6 * Math.Max(1, Math.Abs(a.Value));

    static string Texto(double? v) => v?.ToString("G10", CultureInfo.GetCultureInfo("es-ES")) ?? "(en blanco)";
}
