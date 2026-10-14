// Valida el modelo semántico en TMDL con la biblioteca oficial (TOM) y las reglas del proyecto:
//
//   dotnet run --project validar -- Contratacion.SemanticModel/definition
//
// Sale con 1 si encuentra algún problema. No necesita Power BI ni un servidor de Analysis Services.
//
// Con el proyecto abierto en Power BI Desktop, además (el puerto está en msmdsrv.port.txt):
//
//   dotnet run --project validar -- refrescar <puerto>
//   dotnet run --project validar -- comparar <puerto> datos/cifras.json
//   dotnet run --project validar -- consultar <puerto> "EVALUATE ..." [usuario con el rol Comunidad]

using System.Text.RegularExpressions;
using Microsoft.AnalysisServices.Tabular;

switch (args)
{
    case ["refrescar", var puerto]:
        return Desktop.Refrescar(int.Parse(puerto));
    case ["comparar", var puerto, var cifras]:
        return Desktop.Comparar(int.Parse(puerto), cifras);
    case ["consultar", var puerto, var dax]:
        return Desktop.Consultar(int.Parse(puerto), dax, null);
    case ["consultar", var puerto, var dax, var usuario]:
        return Desktop.Consultar(int.Parse(puerto), dax, usuario);
}

var carpeta = args.Length > 0 ? args[0] : "Contratacion.SemanticModel/definition";

Database database;
try
{
    database = TmdlSerializer.DeserializeDatabaseFromFolder(carpeta);
}
catch (Exception e)
{
    Console.Error.WriteLine($"El TMDL no se puede leer: {e.Message}");
    return 1;
}

var problemas = Reglas.Comprobar(database.Model);
foreach (var problema in problemas)
{
    Console.Error.WriteLine($"- {problema}");
}

var modelo = database.Model;
Console.WriteLine(
    $"{modelo.Tables.Count} tablas, {modelo.Tables.Sum(t => t.Measures.Count)} medidas, "
        + $"{modelo.Relationships.Count} relaciones, {modelo.Roles.Count} roles: "
        + (problemas.Count == 0 ? "sin problemas." : $"{problemas.Count} problemas."));
return problemas.Count == 0 ? 0 : 1;

static partial class Reglas
{
    public static List<string> Comprobar(Model modelo)
    {
        var problemas = new List<string>();
        var medidas = modelo.Tables.SelectMany(t => t.Measures).ToList();

        if (!modelo.DiscourageImplicitMeasures)
        {
            problemas.Add("El modelo tiene que desactivar las medidas implícitas (discourageImplicitMeasures).");
        }

        foreach (var medida in medidas)
        {
            if (string.IsNullOrWhiteSpace(medida.Description))
            {
                problemas.Add($"La medida [{medida.Name}] no tiene descripción.");
            }
            if (string.IsNullOrWhiteSpace(medida.FormatString) && medida.FormatStringDefinition is null)
            {
                problemas.Add($"La medida [{medida.Name}] no tiene formato.");
            }
            if (string.IsNullOrWhiteSpace(medida.DisplayFolder))
            {
                problemas.Add($"La medida [{medida.Name}] no está en ninguna carpeta.");
            }
        }

        foreach (var tabla in modelo.Tables.Where(t => !t.IsHidden && t.CalculationGroup is null && t.Name != "Medidas"))
        {
            if (string.IsNullOrWhiteSpace(tabla.Description))
            {
                problemas.Add($"La tabla '{tabla.Name}' no tiene descripción.");
            }
        }

        foreach (var relacion in modelo.Relationships.OfType<SingleColumnRelationship>())
        {
            var nombre = $"{relacion.FromColumn.Table.Name}[{relacion.FromColumn.Name}] → {relacion.ToColumn.Table.Name}[{relacion.ToColumn.Name}]";
            if (relacion.FromCardinality != RelationshipEndCardinality.Many || relacion.ToCardinality != RelationshipEndCardinality.One)
            {
                problemas.Add($"La relación {nombre} no es de varios a uno.");
            }
            if (relacion.CrossFilteringBehavior != CrossFilteringBehavior.OneDirection)
            {
                problemas.Add($"La relación {nombre} filtra en las dos direcciones.");
            }
            if (!relacion.FromColumn.IsHidden)
            {
                problemas.Add($"La clave {relacion.FromColumn.Table.Name}[{relacion.FromColumn.Name}] está visible: se filtra por la dimensión.");
            }
            if (relacion.FromColumn.DataType != relacion.ToColumn.DataType)
            {
                problemas.Add($"La relación {nombre} une columnas de tipos distintos.");
            }
        }

        var fechas = modelo.Tables.Where(t => t.DataCategory == "Time").ToList();
        if (fechas.Count != 1 || !fechas[0].Columns.Any(c => c.IsKey && c.DataType == DataType.DateTime))
        {
            problemas.Add("Tiene que haber una tabla de fechas marcada (dataCategory Time) con una columna clave de fecha.");
        }

        problemas.AddRange(ComprobarReferencias(modelo));
        return problemas;
    }

    /// <summary>
    /// Cada referencia DAX a una columna ('Tabla'[Columna]) o a una medida ([Medida]) tiene que existir. TOM no
    /// analiza el DAX, así que sin esto una errata en un nombre solo se vería al abrir el informe.
    /// </summary>
    static IEnumerable<string> ComprobarReferencias(Model modelo)
    {
        var columnas = modelo.Tables
            .SelectMany(t => t.Columns.Select(c => (Tabla: t.Name, Nombre: c.Name)))
            .ToHashSet();
        var medidas = modelo.Tables.SelectMany(t => t.Measures).Select(m => m.Name).ToHashSet();
        var tablas = modelo.Tables.Select(t => t.Name).ToHashSet();

        var expresiones = modelo.Tables.SelectMany(t => t.Measures)
            .Select(m => ($"medida [{m.Name}]", m.Expression, (ISet<string>?)null))
            .Concat(modelo.Tables
                .Where(t => t.CalculationGroup is not null)
                .SelectMany(t => t.CalculationGroup.CalculationItems)
                .Select(i => ($"elemento de cálculo «{i.Name}»", i.Expression, (ISet<string>?)null)))
            .Concat(modelo.Roles
                .SelectMany(r => r.TablePermissions)
                .Select(p => ($"rol «{p.Role.Name}»", p.FilterExpression, (ISet<string>?)null)));

        foreach (var (donde, expresion, _) in expresiones)
        {
            // Las variables (VAR Nombre) no son referencias; los textos entre comillas tampoco.
            var dax = Cadenas().Replace(expresion ?? "", "\"\"");
            foreach (Match m in ColumnaCualificada().Matches(dax))
            {
                var tabla = m.Groups["tc"].Success ? m.Groups["tc"].Value.Replace("''", "'") : m.Groups["ts"].Value;
                var columna = m.Groups["c"].Value;
                if (!tablas.Contains(tabla))
                {
                    yield return $"En la {donde}: la tabla '{tabla}' no existe.";
                }
                else if (!columnas.Contains((tabla, columna)))
                {
                    yield return $"En la {donde}: la columna '{tabla}'[{columna}] no existe.";
                }
            }
            var sinColumnas = ColumnaCualificada().Replace(dax, " ");
            foreach (Match m in MedidaSuelta().Matches(sinColumnas))
            {
                var nombre = m.Groups["m"].Value;
                // [Value] es la columna que crea GENERATESERIES; [Top N], la que se le da después.
                if (!medidas.Contains(nombre) && nombre is not "Value")
                {
                    yield return $"En la {donde}: la medida [{nombre}] no existe.";
                }
            }
        }
    }

    [GeneratedRegex("\"(?:[^\"]|\"\")*\"")]
    private static partial Regex Cadenas();

    [GeneratedRegex(@"(?:'(?<tc>(?:[^']|'')+)'|(?<ts>[\p{L}_][\p{L}\p{N}_]*))\s*\[(?<c>[^\]]+)\]")]
    private static partial Regex ColumnaCualificada();

    [GeneratedRegex(@"\[(?<m>[^\]]+)\]")]
    private static partial Regex MedidaSuelta();
}
