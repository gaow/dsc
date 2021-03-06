context("dscrutils")

test_that(paste("First one_sample_location DSC query examples returns a",
                "8 x 4 data frame"),{
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  outfile <- system.file("datafiles","one_sample_location","dsc-query-output.csv",
                         package = "dscrutils")
  capture.output(
    out1 <- dscquery(dsc.dir,targets = c("simulate.n","analyze","score.error"),
                    conditions = "$(simulate.n) > 10"))
  capture.output(
    out2 <- dscquery(dsc.dir,targets = c("simulate.n","analyze","score.error"),
                     conditions = "$(simulate.n) > 10",
                     dsc.outfile = outfile))
  expect_equal(dim(out1),c(8,4))
  expect_equal(dim(out2),c(8,4))
  expect_equal(out1,out2)
})

test_that(paste("Filtering by conditions argument for one_sample_location",
                "DSC query gives same result as filtering with subset"),{

  # Retrieve results from all simulations.                  
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  capture.output(
    dat1 <- dscquery(dsc.dir,targets = c("simulate.n","analyze","score.error")))

  # Retrieve results only for simulations in which the "mean" module
  # was run.
  capture.output(
    dat2 <- dscquery(dsc.dir,targets = c("simulate.n","analyze","score.error"),
                     conditions = "$(analyze) == 'mean'"))
  expect_equal(subset(dat1,analyze == "mean"),dat2,
               check.attributes = FALSE)

  # Retrieve results only for simulations in which the error summary
  # is greater than 0.25.
  capture.output(
    dat3 <- dscquery(dsc.dir,targets = c("simulate.n","analyze","score.error"),
                     conditions = "$(score.error) > 0.25"))
  expect_equal(subset(dat1,score.error > 0.25),dat3,
               check.attributes = FALSE)

  # Retrieve the DSC results only for simulations in which the "mean"
  # module was run, and which which the error summary is greater than
  # 0.25.
  capture.output(
    dat4 <- dscquery(dsc.dir,targets = c("simulate.n","analyze","score.error"),
                     conditions = c("$(score.error) > 0.25",
                                  "$(analyze) == 'median'")))
  expect_equal(subset(dat1,analyze == "median" & score.error > 0.25),
               dat4,check.attributes = FALSE)
})

test_that(paste("dscquery correctly allows condition targets that are",
                "names of module groups"),{
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  capture.output(dat <- dscquery(dsc.dir,
                                 targets = c("simulate.n","score.error"),
                                 conditions = c("$(simulate) == 't'")))
  expect_equal(dim(dat),c(4,3))
})

test_that("ash DSC query example returns a 10 x 6 data frame",{

  # Retrieve some results from the "ash" DSC experiment. In this
  # example, the beta estimates are long vectors (of length one
  # thousand), so the results are not returned in a data frame.
  dsc.dir <- system.file("datafiles","ash","dsc_result",package = "dscrutils")
  capture.output(
    dat <- dscquery(dsc.dir,
      targets = c(paste("simulate",c("nsamp","g"),sep="."),
                  paste("shrink",c("mixcompdist","beta_est","pi0_est"),sep = ".")),
      conditions="$(simulate.g) =='list(c(2/3,1/3),c(0,0),c(1,2))'"))
  expect_false(is.data.frame(dat))
  expect_equal(length(dat),6)
})

test_that(paste("Second ash DSC example without shrink.beta_est returns a",
                "data frame"),{

  # This is the same as the previous example, but extracts the
  # vector-valued beta estimates into the outputted data frame. As a
  # result, the data frame of query results is much larger (it has over
  # 1000 columns).
  dsc.dir <- system.file("datafiles","ash","dsc_result",package = "dscrutils")
  capture.output(
    dat <- dscquery(dsc.dir,
      targets = c("simulate.nsamp","simulate.g","shrink.mixcompdist",
                  "shrink.pi0_est"),
      conditions ="$(simulate.g) == 'list(c(2/3,1/3),c(0,0),c(1,2))'"))
  expect_true(is.data.frame(dat))
  expect_equal(dim(dat),c(2,5))
})

test_that(paste("Second one_sample_location DSC example returns an error",
                "because score.mse does not exist"),{

  # This query should generate an error because there is no output
  # called "score" in the "mse" module.
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  expect_error(dscquery(dsc.dir,
                        targets = c("simulate.n","analyze","score.mse"),
                        conditions = "$(simulate.n) > 10",verbose = FALSE))
})

test_that(paste("dscquery appropriately handles unassigned targets when",
                "other targets are scalars"),{
  dat <- data.frame(DSC                     = c(1,2,1,2),
                    sim_params.params_store = c(NA,NA,5,5),
                    cause.z                 = c(0.25,0.25,NA,NA))
  dsc.dir <- system.file("datafiles","misc","results1",package = "dscrutils")
  capture.output(
    out <- dscquery(dsc.dir,targets = c("sim_params.params_store","cause.z")))
  expect_equal(dat,out)
  expect_equal(is.na(dat),is.na(out))
})

test_that(paste("dscquery appropriately handles unassigned targets when",
                "other targets are vectors"),{
  dat <- list(DSC                     = c(1,2,1,2),
              sim_params.params_store = list(NA,NA,1:20,1:20),
              cause.z                 = c(0.25,0.25,NA,NA))
  dsc.dir <- system.file("datafiles","misc","results2",package = "dscrutils")
  capture.output(
    out <- dscquery(dsc.dir,targets = c("sim_params.params_store","cause.z")))
  expect_equal(dat,out)
})

test_that(paste("dscquery throws an error when targets mentioned in",
                "conditions are not included in targets or targets.notreq",
                "arguments"),{
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  expect_error(dscquery(dsc.dir,targets = c("simulate.true_mean"),
                        conditions = "$(score.error) < 1",verbose = FALSE))
})

test_that(paste("dscquery filtering by condition works when return value is",
                "a list, and some columns are complex, while others are not"),{
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  capture.output(
    out <- dscquery(dsc.dir,targets = c("analyze","simulate.data","score.error"),
                    conditions = c("$(analyze) == 'mean'","$(score.error) < 0.2")))
  expect_equivalent(sapply(out,length),rep(2,4))
})

test_that(paste("dscquery returns a data frame with the correct column names",
                "even when the result is empty"),{ 
  dsc.dir <- system.file("datafiles","misc","results1",package = "dscrutils")
  dat        <- as.data.frame(matrix(0,0,3))
  names(dat) <- c("DSC","sim_params.params_store","cause.z")
  cdn <- "!is.na($(sim_params.params_store)) & !is.na($(cause.z))"
  capture.output(
    out <- dscquery(dsc.dir,targets = c("sim_params.params_store","cause.z"),
                    conditions = cdn))
  expect_equal(dat,out)
})

test_that(paste("dscquery adds output.file column when a module group is",
                "included in 'targets' and 'module.output.file' arguments"),{
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  capture.output(dat <- dscquery(dsc.dir,targets = "analyze",
                                 module.output.file = "analyze"))
  expect_equal(names(dat),c("DSC","analyze","analyze.output.file"))
})

test_that(paste("dscquery generates error when module is included in",
                "'module.output.file' or 'module.output.all' input arguments",
                " but not 'targets'"),{
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  expect_error(dscquery(dsc.dir,targets = "score",module.output.file = "analyze",
                        verbose = FALSE))
  expect_error(dscquery(dsc.dir,targets = "score",module.output.all = "analyze",
                        verbose = FALSE))
})

test_that(paste("dscquery does not add corresponding module group name",
                "when 'group.variable' target is requested"),{
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  capture.output(dat <- dscquery(dsc.dir,targets = "score.error"))
  expect_equal(names(dat),c("DSC","score.error"))
})

test_that("dscquery list and data frame contents are the same",{
  dsc.dir <- system.file("datafiles","one_sample_location","dsc_result",
                         package = "dscrutils")
  capture.output(
    out1 <- dscquery(dsc.dir,targets = c("simulate.n","analyze","score.error"),
                     return.type = "data.frame"))
  capture.output(
    out2 <- dscquery(dsc.dir,targets = c("simulate.n","analyze","score.error"),
                     return.type = "list"))
  expect_equal(out1,as.data.frame(out2,stringsAsFactors = FALSE))
})

test_that(paste("dscquery properly handles modules outputs and module",
                "parameters when they are NULL"),{
  dsc.dir <- system.file("datafiles","null_output","null_output",
                         package = "dscrutils")
  dat1 <- data.frame(DSC   = rep(1:4,each = 2),
                     foo.a = rep(c("NULL","4"),times = 2),
                     stringsAsFactors = FALSE)
  dat2 <- list(DSC = 1:4,bar.data = list(NULL,NULL,NULL,0.2167549))
  capture.output(out1 <- dscquery(dsc.dir,"foo.a"))
  capture.output(out2 <- dscquery(dsc.dir,"bar.data"))
  expect_equal(out1,dat1)
  expect_equal(out2,dat2,tolerance = 1e-6)
})
