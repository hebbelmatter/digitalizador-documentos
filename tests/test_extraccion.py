from digitalizador import extraccion as ex


def test_digito_verificador():
    assert ex.digito_verificador(11111111) == "1"
    assert ex.digito_verificador(12345678) == "5"
    assert ex.rut_valido("12.345.678-5")
    assert not ex.rut_valido("12.345.678-9")


def test_buscar_ruts_filtra_invalidos():
    texto = "RUN: 12.345.678-5  otro 12345678-9  apoderado 11.111.111-1"
    assert ex.buscar_ruts(texto) == ["12.345.678-5", "11.111.111-1"]


def test_fechas():
    texto = "Santiago, 3 de marzo de 2025. Nacimiento: 14/07/2012"
    assert ex.buscar_fechas(texto) == ["2025-03-03", "2012-07-14"]


def test_nombre():
    assert ex.buscar_nombre("Nombre del alumno: MARÍA JOSÉ PÉREZ SOTO\nRUT 1-9") == "María José Pérez Soto"
    assert ex.buscar_nombre("Nombres: Juan Pablo González Rojas RUT 12.345.678-5") == "Juan Pablo González Rojas"
    # Valor en la línea siguiente y etiqueta previa sin valor
    texto = "Se certifica que el(la) alumno(a):\n\nNombre del alumno:\n\nMARÍA JOSÉ PÉREZ SOTO\n\nRUN: 1-9"
    assert ex.buscar_nombre(texto) == "María José Pérez Soto"
    assert ex.buscar_nombre("Certifico que don Juan Pablo González Rojas, RUT 1-9") == "Juan Pablo González Rojas"
    assert ex.buscar_nombre("Nombre: MARÍA DE LOS ÁNGELES ROJAS") == "María de los Ángeles Rojas"
    assert ex.buscar_nombre("Firma del postulante") == ""


def test_correo_telefono():
    t = "Correo: Ana.Diaz@Gmail.com  Fono +56 9 8765 4321"
    assert ex.buscar_correos(t) == ["ana.diaz@gmail.com"]
    assert ex.buscar_telefonos(t) == ["+56987654321"]


def test_clasificar():
    assert ex.clasificar("CERTIFICADO ANUAL DE ESTUDIOS ... promedio 6,2") == "certificado_notas"
    assert ex.clasificar("Certificado de alumno regular") == "certificado_alumno_regular"
    assert ex.clasificar("hola") == "otro"
